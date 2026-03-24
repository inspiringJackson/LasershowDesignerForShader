import json
from typing import List, Dict, Any, Optional
from .llm_adapter import AdapterFactory
from .agent import Agent
from .laser_tools import LaserAgentTools
from .math_agent import get_math_tools, MathAgentTools

# ====== 系统提示词定义 ======

MAIN_AGENT_PROMPT = """你是一个专业的激光秀设计主控助手（Main Agent）。
你的任务是理解用户意图，并将任务合理分配给专业子Agent，或直接回答普通问题。
你具备记忆功能，可以记住用户的偏好和上下文。

【你的可用子Agent】
1. 光源管理Agent：专门负责在场景中添加、移除、修改激光光源，设置阵列同步等。如果你需要操作激光场景，必须调用 delegate_to_laser_agent 工具。
2. 计算型Agent：专门负责复杂的数学计算、几何点位计算（如计算圆上的点位坐标、矩阵变换等）。如果遇到复杂的几何计算需求，请调用 delegate_to_math_agent 工具获取计算结果，然后再将结果交给光源管理Agent使用。

【工作原则】
1. 当用户要求执行具体的光源操作时，先评估是否需要复杂的几何/数学计算。如果需要，先委托给计算型Agent。
2. 将明确的参数（坐标列表、颜色等）整理好后，再委托给光源管理Agent。
3. 委托子Agent时，请在 instruction 中给出尽可能详细的指令，说明他们需要完成什么具体任务。
4. 子Agent执行完成后会将结果返回给你，你可以据此继续分配任务或回复用户。
5. 当你认为所有任务已经完成时，直接向用户总结你完成了什么。
"""

LASER_AGENT_PROMPT = """你是一个专门负责光源设备管理、场景布光的Agent。
你的任务是接收主Agent的指令，并调用激光光源管理工具来完成操作。

【参数约束】
- 位置 (pos): 空间坐标，通常在 -3000 到 3000 之间。
- 方向 (dir / dir_vec): 向量 [x, y, z]，通常为归一化或在 -1.0 到 1.0 之间。
- 颜色 (color): [r, g, b]，取值范围必须在 0.0 到 1.0 之间。
- 亮度 (brightness): 0.0 到 10.0。
- 光束粗细 (thickness): 0.0 到 100.0。
- 发散角 (divergence): 弧度值，通常由角度转换而来。
- 衰减系数 (attenuation): 0.0 到 1.0 之间，默认 0.1。
- 额外参数 (params): [x, y, z, w] 四维向量，不同光源类型用途不同。
- 上向量 (local_up): 向量 [x, y, z]，通常为 [0.0, 0.0, 1.0]。
- 光源类型 (laser_type): 0=单束(Beam), 1=扇面(Fan), 2=图案(Pattern), 3=粒子(Particle), 4=实体扇面(SolidFan)。

【工作原则】
1. 严格遵守主Agent提供的参数要求。
2. 操作完成后，必须调用 finish_task_and_return 工具将结果和你的操作总结返回给主Agent，并交出控制权。
"""

MATH_AGENT_PROMPT = """你是一个专门负责复杂数学计算和几何运算的Agent。
你的任务是接收主Agent的计算请求，调用 python_calculator 工具进行计算。

【工作原则】
1. 编写正确的Python代码解决几何或数学问题。可以使用 math 和 numpy 库。
2. 请将计算出的最终结果赋值给名为 result 的变量，或者使用 print() 打印出来。
3. 得到满意的计算结果后，必须调用 finish_task_and_return 工具将结果返回给主Agent，并交出控制权。如果遇到错误可以重新尝试调用工具修改代码。
"""

# ====== 工具模式定义 ======

def get_laser_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "add_laser",
                "description": "在场景中添加一个新的激光光源",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "激光器的唯一名称"},
                        "laser_type": {"type": "integer", "description": "0=单束, 1=扇面, 2=图案, 3=粒子, 4=实体扇面"},
                        "pos": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z] 位置坐标"},
                        "dir_vec": {"type": "array", "items": {"type": "number"}, "description": "[dx, dy, dz] 方向向量"},
                        "color": {"type": "array", "items": {"type": "number"}, "description": "[r, g, b] 颜色值，范围 0.0-1.0"},
                        "brightness": {"type": "number", "description": "亮度，0.0-10.0"},
                        "thickness": {"type": "number", "description": "光束粗细"},
                        "divergence": {"type": "number", "description": "发散角(弧度)"},
                        "attenuation": {"type": "number", "description": "衰减系数(默认0.1)"},
                        "params": {"type": "array", "items": {"type": "number"}, "description": "[x, y, z, w] 额外参数"},
                        "local_up": {"type": "array", "items": {"type": "number"}, "description": "[ux, uy, uz] 上向量(默认[0,0,1])"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "remove_laser",
                "description": "移除指定名称的激光光源",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "要移除的激光器名称"}
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_laser_properties",
                "description": "批量修改激光光源的属性",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "激光器名称"},
                        "properties": {
                            "type": "object",
                            "description": "键值对，键为属性名（如 pos.x, color.r, brightness, pos(数组), color(数组), dir(数组), localUp(数组), params(数组), divergence 等），值为新的数值。"
                        }
                    },
                    "required": ["name", "properties"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_laser_type",
                "description": "更改激光光源的类型",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "激光器名称"},
                        "laser_type": {"type": "integer", "description": "0=单束, 1=扇面, 2=图案, 3=粒子, 4=实体扇面"}
                    },
                    "required": ["name", "laser_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "setup_master_slave",
                "description": "配置主从阵列同步系统，将多个灯光绑定为主控灯的从属灯，并设置参数偏移量",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "master_name": {"type": "string", "description": "主控灯名称"},
                        "subordinate_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "从属灯名称列表"
                        },
                        "offset_params": {
                            "type": "object",
                            "description": "参数偏移量字典，例如 {'pos.x': 100.0, 'color.r': 0.1}"
                        },
                        "offset_modes": {
                            "type": "object",
                            "description": "参数偏移模式字典，0=相对从属, 1=相对主控。例如 {'pos.x': 1}"
                        }
                    },
                    "required": ["master_name", "subordinate_names"]
                }
            }
        }
    ]

def get_main_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "delegate_to_laser_agent",
                "description": "将涉及光源操作、参数设置、场景布光的任务委托给光源管理Agent执行。调用此工具后，当前任务将移交给该Agent。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "详细说明需要光源Agent执行的任务，包含坐标、颜色等具体参数"}
                    },
                    "required": ["instruction"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delegate_to_math_agent",
                "description": "将涉及复杂数学计算、几何点位计算的任务委托给计算型Agent执行。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "instruction": {"type": "string", "description": "说明需要计算的具体数学问题，如'计算半径500圆上的10个点位'"}
                    },
                    "required": ["instruction"]
                }
            }
        }
    ]

def get_finish_tool() -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "finish_task_and_return",
            "description": "当前Agent完成任务后，调用此工具将结果返回给主Agent，并交还控制权。",
            "parameters": {
                "type": "object",
                "properties": {
                    "result_summary": {"type": "string", "description": "任务执行结果的总结，包含必要的数据供主Agent使用"}
                },
                "required": ["result_summary"]
            }
        }
    }


class MultiAgentCore:
    def __init__(self, main_window, provider: str = "deepseek"):
        self.main_window = main_window
        self.provider = provider
        
        self.laser_tools_api = LaserAgentTools(main_window)
        self.math_tools_api = MathAgentTools()
        
        self.init_agents()
        
    def init_agents(self):
        # 初始化三个 Agent
        self.main_agent = Agent("主Agent", MAIN_AGENT_PROMPT, get_main_tools(), self.provider)
        self.laser_agent = Agent("光源Agent", LASER_AGENT_PROMPT, get_laser_tools() + [get_finish_tool()], self.provider)
        self.math_agent = Agent("计算Agent", MATH_AGENT_PROMPT, get_math_tools() + [get_finish_tool()], self.provider)
        
        self.active_agent = self.main_agent

    def execute_tool(self, func_name: str, args: Dict[str, Any]) -> Any:
        try:
            # Main Agent Tools
            if func_name == "delegate_to_laser_agent":
                instruction = args.get("instruction", "")
                self.laser_agent.messages.append({"role": "user", "content": f"主Agent交办任务：\n{instruction}"})
                self.active_agent = self.laser_agent
                return {"success": True, "message": f"任务已转交给 {self.laser_agent.name}"}
                
            elif func_name == "delegate_to_math_agent":
                instruction = args.get("instruction", "")
                self.math_agent.messages.append({"role": "user", "content": f"主Agent交办任务：\n{instruction}"})
                self.active_agent = self.math_agent
                return {"success": True, "message": f"任务已转交给 {self.math_agent.name}"}

            # Sub-Agent Return Tool
            elif func_name == "finish_task_and_return":
                result = args.get("result_summary", "")
                agent_name = self.active_agent.name
                self.main_agent.messages.append({"role": "user", "content": f"{agent_name} 返回了执行结果：\n{result}"})
                self.active_agent = self.main_agent
                return {"success": True, "message": f"控制权已交还主Agent"}

            # Math Tools
            elif func_name == "python_calculator":
                return self.math_tools_api.execute(func_name, args)

            # Laser Tools
            elif func_name in ["add_laser", "remove_laser", "set_laser_properties", "set_laser_type", "setup_master_slave"]:
                if func_name == "add_laser":
                    res = self.laser_tools_api.add_laser(**args)
                    return {"success": res, "message": "Success" if res else "Name already exists"}
                elif func_name == "remove_laser":
                    res = self.laser_tools_api.remove_laser(**args)
                    return {"success": res, "message": "Success" if res else "Laser not found"}
                elif func_name == "set_laser_properties":
                    res = self.laser_tools_api.set_laser_properties(**args)
                    return {"success": res, "message": "Success" if res else "Laser not found"}
                elif func_name == "set_laser_type":
                    res = self.laser_tools_api.set_laser_type(**args)
                    return {"success": res, "message": "Success" if res else "Laser not found"}
                elif func_name == "setup_master_slave":
                    res = self.laser_tools_api.setup_master_slave(**args)
                    return {"success": res, "message": "Success" if res else "Master laser not found"}
                    
            return {"success": False, "message": f"Unknown tool {func_name}"}
            
        except Exception as e:
            return {"success": False, "message": str(e)}

    def clear_history(self):
        self.main_agent.clear_history()
        self.laser_agent.clear_history()
        self.math_agent.clear_history()
        self.active_agent = self.main_agent
