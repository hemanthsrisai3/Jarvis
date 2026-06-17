import os
import importlib.util
import logging
import inspect
from typing import Dict, List, Any
from tools.base import BaseTool

logger = logging.getLogger("jarvis.tools")

class ToolRegistry:
    """
    Dynamically loads and manages tool execution for J.A.R.V.I.S.
    """
    def __init__(self) -> None:
        self.tools: Dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a single tool instance.
        """
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: '{tool.name}'")

    def load_tools(self) -> None:
        """
        Dynamically scan and import all tool classes in the tools folder.
        """
        self.tools.clear()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        logger.info(f"Scanning tools directory: {current_dir}")
        for file in os.listdir(current_dir):
            if file.endswith(".py") and file not in ("__init__.py", "base.py", "registry.py"):
                module_name = file[:-3]
                module_path = os.path.join(current_dir, file)
                
                try:
                    # Dynamically load module
                    spec = importlib.util.spec_from_file_location(f"tools.{module_name}", module_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Register classes inheriting from BaseTool
                        for _, obj in inspect.getmembers(module, inspect.isclass):
                            if issubclass(obj, BaseTool) and obj is not BaseTool:
                                try:
                                    tool_instance = obj()
                                    self.register_tool(tool_instance)
                                except Exception as inst_err:
                                    logger.error(f"Failed to instantiate tool class in {file}: {inst_err}")
                except Exception as e:
                    logger.error(f"Failed to dynamically load tool module '{module_name}': {e}")
        
        logger.info(f"Loaded {len(self.tools)} tools: {list(self.tools.keys())}")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Format tool descriptions as JSON schema for LLM tool calling.
        """
        definitions = []
        for tool in self.tools.values():
            definitions.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                }
            })
        return definitions

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """
        Execute tool safely, returning formatted error messages on exceptions.
        """
        # Alias resolution
        alias_map = {
            "clock": "clock_app",
            "clock_ops": "clock_app",
            "clock_manager": "clock_app",
            "timer": "clock_app",
            "alarm": "clock_app"
        }
        if name in alias_map:
            logger.info(f"Resolving alias: '{name}' -> '{alias_map[name]}'")
            name = alias_map[name]

        if name not in self.tools:
            logger.warning(f"Requested tool '{name}' not found in registry.")
            return f"Error: Tool '{name}' is not registered."

        tool = self.tools[name]
        logger.info(f"Executing tool '{name}' with arguments: {args}")
        try:
            result = await tool.run(**args)
            return str(result)
        except TypeError as type_err:
            msg = f"Error: Tool '{name}' argument mismatch. Details: {type_err}"
            logger.error(msg)
            return msg
        except Exception as e:
            msg = f"Error during execution of tool '{name}': {e}"
            logger.error(msg, exc_info=True)
            return msg

# Shared instance
registry = ToolRegistry()
# Auto-load on import
registry.load_tools()
