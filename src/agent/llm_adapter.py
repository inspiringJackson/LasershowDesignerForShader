import os
from typing import List, Dict, Any, Optional
from openai import OpenAI

class LLMAdapter:
    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        raise NotImplementedError

class OpenAILikeAdapter(LLMAdapter):
    def __init__(self, api_key: str, base_url: str, model_name: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Any:
        kwargs = {
            "model": self.model_name,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message

class AdapterFactory:
    @staticmethod
    def create_adapter(provider: str) -> LLMAdapter:
        if provider.lower() == "deepseek":
            api_key = os.getenv("DEEPSEEK_API_KEY", "")
            if not api_key:
                print("Warning: DEEPSEEK_API_KEY not found in environment variables.")
            return OpenAILikeAdapter(
                api_key=api_key,
                base_url="https://api.deepseek.com",
                model_name="deepseek-chat"
            )
        elif provider.lower() == "openai":
            api_key = os.getenv("OPENAI_API_KEY", "")
            return OpenAILikeAdapter(
                api_key=api_key,
                base_url="https://api.openai.com/v1",
                model_name="gpt-4o"
            )
        elif provider.lower() == "qwen":
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            return OpenAILikeAdapter(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                model_name="qwen-max"
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")
