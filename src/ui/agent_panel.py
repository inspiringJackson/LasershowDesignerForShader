from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTextEdit, 
                               QLineEdit, QPushButton, QHBoxLayout, QLabel)
from PySide6.QtCore import Qt, QThread, Signal, QMetaObject, Q_ARG
from agent.core import MultiAgentCore
import json

class AgentWorker(QThread):
    # Signals for different types of LLM responses
    text_reply_signal = Signal(str, str) # Added agent_name
    tool_calls_signal = Signal(object, str) # Passes response_msg and agent_name
    error_signal = Signal(str)

    def __init__(self, core: MultiAgentCore):
        super().__init__()
        self.core = core
        self.is_running = True

    def run(self):
        try:
            active_agent = self.core.active_agent
            agent_name = active_agent.name
            
            response_msg = active_agent.llm.chat(active_agent.messages, tools=active_agent.tools)
            
            # Save assistant message to history
            active_agent.messages.append(response_msg.model_dump(exclude_none=True))
            
            if response_msg.tool_calls:
                self.tool_calls_signal.emit(response_msg, agent_name)
            else:
                self.text_reply_signal.emit(response_msg.content or "", agent_name)
                
        except Exception as e:
            self.error_signal.emit(str(e))

class AgentPanel(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.agent_core = MultiAgentCore(main_window, provider="deepseek")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Header
        header = QLabel("💡 AI 激光秀助手")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Chat History
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #444;")
        layout.addWidget(self.chat_history)

        # Input Area
        input_layout = QHBoxLayout()
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("告诉助手你想要什么效果...")
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)
        
        # Initial greeting
        self.append_message("🤖 助手", "你好！我是激光秀设计助手。你可以让我帮你添加灯光、调整颜色、设置阵列效果等。试试对我说：'在中间添加一个红色的扇面激光'。")

    def append_message(self, sender: str, message: str):
        color = "#5c9ded" if sender == "🧑 你" else "#4caf50"
        if sender == "🛠️ 工具":
            color = "#ff9800"
        self.chat_history.append(f"<b style='color:{color}'>{sender}:</b> <br>{message}<br>")
        # Scroll to bottom
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def send_message(self):
        text = self.input_field.text().strip()
        if not text:
            return

        self.input_field.clear()
        self.append_message("🧑 你", text)
        
        # Add user message to active agent
        self.agent_core.active_agent.messages.append({"role": "user", "content": text})
        
        self.start_agent_worker()

    def start_agent_worker(self):
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        # Add thinking indicator
        self.chat_history.append("<i style='color:#888' id='thinking'>思考中...</i>")

        # Start worker thread
        self.worker = AgentWorker(self.agent_core)
        self.worker.text_reply_signal.connect(self.on_agent_text_reply)
        self.worker.tool_calls_signal.connect(self.on_agent_tool_calls)
        self.worker.error_signal.connect(self.on_agent_error)
        self.worker.start()

    def remove_thinking_indicator(self):
        text = self.chat_history.toHtml()
        text = text.replace("<i style=\"color:#888\" id=\"thinking\">思考中...</i>", "")
        self.chat_history.setHtml(text)
        # Scroll to bottom
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_agent_text_reply(self, reply: str, agent_name: str):
        self.remove_thinking_indicator()
        self.append_message(f"🤖 {agent_name}", reply)
        self.enable_input()

    def on_agent_tool_calls(self, response_msg, agent_name: str):
        self.remove_thinking_indicator()
        
        # Keep track of the agent that initiated the tool calls
        agent_that_called = self.agent_core.active_agent
        
        # We are back on the MAIN THREAD! Safe to execute tools.
        for tool_call in response_msg.tool_calls:
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                func_args = {}
            
            self.append_message("🛠️ 工具", f"[{agent_name}] 调用: {func_name}({json.dumps(func_args, ensure_ascii=False)})")
            
            # Execute tool
            result = self.agent_core.execute_tool(func_name, func_args)
            
            # Add tool result to history of the agent that called the tool
            agent_that_called.messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": json.dumps(result, ensure_ascii=False)
            })
            
            status = "成功" if result.get("success") else "失败"
            self.append_message("🛠️ 工具", f"[{agent_name}] 结果: {status} - {result.get('message', '')}")
            
        # Restart worker to let LLM summarize or continue
        self.start_agent_worker()

    def on_agent_error(self, error: str):
        self.remove_thinking_indicator()
        self.append_message("❌ 系统错误", f"与大模型通信失败: {error}")
        self.enable_input()

    def enable_input(self):
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_field.setFocus()
