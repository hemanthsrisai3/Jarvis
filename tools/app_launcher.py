import os
import subprocess
import logging
import re
import shlex
from typing import Dict, Any
from tools.base import BaseTool
from config.settings import settings

logger = logging.getLogger("jarvis.tools.app_launcher")

# Safe predefined applications mapped to their standard Windows executable names
SAFE_APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe"
}

class AppLauncherTool(BaseTool):
    """
    Safely launches system or local applications on the host machine.
    """
    @property
    def name(self) -> str:
        return "app_launcher"

    @property
    def description(self) -> str:
        return (
            "Safely launches registered applications or user executables on the host. "
            "Supported shorthand names: 'notepad', 'calculator', 'paint', 'explorer', 'chrome', 'edge'. "
            "Supports absolute paths to other executables (e.g. 'C:\\Program Files\\...\\app.exe'). "
            "Shell scripting and chaining are blocked for security."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Predefined application shorthand (e.g., 'notepad', 'chrome', 'calculator') or an absolute path to the executable."
                },
                "arguments": {
                    "type": "string",
                    "description": "Optional arguments to pass (e.g., a file path to open in Notepad or a URL to load in Chrome). Shell metacharacters are stripped."
                }
            },
            "required": ["app_name"],
            "additionalProperties": False
        }

    async def run(self, **kwargs) -> str:
        app_name = kwargs.get("app_name", "").strip()
        args_str = kwargs.get("arguments", "").strip()

        if not app_name:
            return "Error: No application name or path provided."

        # 1. Resolve Executable Path
        exec_name = SAFE_APP_MAP.get(app_name.lower())
        if not exec_name:
            # If not in shorthand map, verify if it is a valid absolute path to a .exe or shortcut
            clean_path = app_name.replace('"', '').replace("'", "")
            if os.path.isabs(clean_path) or clean_path.endswith(".exe"):
                if os.path.exists(clean_path):
                    if clean_path.lower().endswith((".exe", ".lnk")):
                        exec_name = clean_path
                    else:
                        return f"Access Denied: File '{clean_path}' is not a valid executable (.exe) or shortcut (.lnk)."
                else:
                    return f"Error: Executable path '{clean_path}' does not exist."
            else:
                supported_apps = ", ".join(SAFE_APP_MAP.keys())
                return f"Access Denied: '{app_name}' is not in the allowed shorthand list ({supported_apps}), and is not a valid absolute path."

        # 2. Argument Sanitization
        # Block command injection characters
        forbidden_chars = r"[&|;><`\$\n\r]"
        if re.search(forbidden_chars, args_str):
            logger.warning(f"Security Alert: Blocked app launch due to command injection symbols in args: '{args_str}'")
            return "Security Alert: Launch aborted. Arguments contain forbidden shell execution characters."

        cmd = [exec_name]
        if args_str:
            try:
                # Parse arguments safely keeping quoted arguments intact
                parsed_args = shlex.split(args_str, posix=False)
                cmd.extend(parsed_args)
            except Exception:
                cmd.append(args_str)

        # 3. Launch Process Securely (shell=False)
        try:
            logger.info(f"Secure app launch command: {cmd}")
            subprocess.Popen(cmd, shell=False)
            return f"Successfully launched '{app_name}' securely."
        except Exception as e:
            logger.error(f"Failed to launch app securely: {e}", exc_info=True)
            return f"Error launching application: {str(e)}"
