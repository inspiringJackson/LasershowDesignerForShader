from typing import List, Dict, Any
import math
import numpy as np

def get_math_tools() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "python_calculator",
                "description": "执行一段Python代码来进行复杂的数学或几何计算。你可以使用 math 和 np (numpy) 库。必须将最终结果赋值给变量 'result'，或者使用 print() 打印出来。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string", 
                            "description": "要执行的Python代码。例如：\nimport math\nresult = [math.sin(i) for i in range(10)]"
                        }
                    },
                    "required": ["code"]
                }
            }
        }
    ]

class MathAgentTools:
    def execute(self, func_name: str, args: Dict[str, Any]) -> Any:
        if func_name == "python_calculator":
            return self.python_calculator(args.get("code", ""))
        return {"success": False, "message": f"Unknown tool {func_name}"}

    def python_calculator(self, code: str) -> Dict[str, Any]:
        import sys
        import io
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        local_env = {"math": math, "np": np}
        try:
            exec(code, local_env)
            output = sys.stdout.getvalue()
            result = local_env.get('result', None)
            
            # Formulate response
            res_str = ""
            if output:
                res_str += f"输出:\n{output}\n"
            if result is not None:
                res_str += f"Result变量:\n{result}"
                
            if not res_str:
                res_str = "代码执行成功，但没有输出或 result 变量"
                
            return {"success": True, "result": res_str}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            sys.stdout = old_stdout
