from typing import List, Dict, Any
from .llm_adapter import AdapterFactory

class Agent:
    def __init__(self, name: str, system_prompt: str, tools: List[Dict[str, Any]], provider: str = "deepseek"):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.llm = AdapterFactory.create_adapter(provider)
        self.messages = [{"role": "system", "content": system_prompt}]

    def clear_history(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
