import os
import glob
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List
from tools.base import BaseTool
from config.settings import settings

logger = logging.getLogger("jarvis.tools.file_ops")

def _fast_search_sync(start_dir: Path, query_str: str, max_results: int = 50) -> List[str]:
    """
    Traverses directories using fast os.scandir, skipping bulky system/dependency directories.
    """
    results = []
    # Directories to skip for speed and safety
    skip_dirs = {
        "node_modules", ".git", ".venv", "venv", "env", ".next", 
        "AppData", "Local Settings", "System Volume Information",
        "$Recycle.Bin", "Microsoft", "Windows"
    }
    
    query_lower = query_str.lower().strip()
    is_extension_check = query_str.startswith("*.")
    ext = query_str[1:].lower() if is_extension_check else ""
    
    stack = [start_dir]
    
    while stack and len(results) < max_results:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name not in skip_dirs and not entry.name.startswith("."):
                            stack.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        name_lower = entry.name.lower()
                        if is_extension_check:
                            if name_lower.endswith(ext):
                                results.append(entry.path)
                        else:
                            if query_lower in name_lower:
                                results.append(entry.path)
        except PermissionError:
            continue
        except Exception:
            continue
            
    return results

class FileOpsTool(BaseTool):
    """
    Reads, writes, lists, deletes, or searches files anywhere on the local computer.
    """
    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return (
            "Performs file operations (read, write, list, delete, search) anywhere on the host machine. "
            "Supports absolute paths (e.g., 'C:\\Users\\...' or 'D:\\...') and relative paths. "
            "Use 'search' to locate files quickly across directories by filename or extension."
        )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete", "search"],
                    "description": "The file operation to execute."
                },
                "path": {
                    "type": "string",
                    "description": "The file path or directory to operate on. For 'search', this is the starting directory."
                },
                "content": {
                    "type": "string",
                    "description": "The text content to write. Required only when action is 'write'."
                },
                "query": {
                    "type": "string",
                    "description": "The search keyword or extension (e.g., 'invoice' or '*.pdf') to search for. Required only when action is 'search'."
                }
            },
            "required": ["action", "path"],
            "additionalProperties": False
        }

    async def run(self, **kwargs) -> str:
        action = kwargs.get("action")
        path_str = kwargs.get("path", "")
        content = kwargs.get("content", "")
        query = kwargs.get("query", "")

        try:
            target_path = Path(path_str)
            if not target_path.is_absolute():
                base_path = Path(settings.WORKSPACE_DIR).resolve()
                target_path = Path(os.path.normpath(os.path.join(base_path, path_str))).resolve()
            else:
                target_path = target_path.resolve()
        except Exception as e:
            return f"Error parsing path '{path_str}': {e}"

        logger.info(f"File operation: action={action}, path={target_path}")

        if action == "read":
            if not target_path.exists():
                return f"Error: File '{target_path}' does not exist."
            if not target_path.is_file():
                return f"Error: '{target_path}' is not a file."
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                if target_path.suffix.lower() in (".exe", ".dll", ".lnk", ".sys", ".bin"):
                    return (
                        f"Error: '{target_path}' is a binary executable/system file. "
                        "You cannot read its content as text. If you intended to run this application, "
                        "please use the 'app_launcher' tool instead."
                    )
                return f"Error: '{target_path}' is a binary file (not readable as UTF-8 text)."
            except Exception as e:
                return f"Error reading file '{target_path}': {str(e)}"

        elif action == "write":
            try:
                parent_dir = target_path.parent.resolve()
                os.makedirs(parent_dir, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return f"Successfully wrote to file '{target_path}'."
            except Exception as e:
                return f"Error writing to file '{target_path}': {str(e)}"

        elif action == "list":
            try:
                if target_path.is_dir():
                    search_pattern = os.path.join(target_path, "*")
                else:
                    search_pattern = str(target_path)
                
                matched_items = await asyncio.to_thread(glob.glob, search_pattern, recursive=True)
                files = []
                
                for item in matched_items:
                    item_path = Path(item).resolve()
                    label = "dir" if item_path.is_dir() else "file"
                    files.append(f"[{label}] {item_path}")
                
                if not files:
                    return f"No items found matching '{path_str}'."
                return "\n".join(files)
            except Exception as e:
                return f"Error listing files at '{path_str}': {str(e)}"

        elif action == "search":
            if not target_path.exists():
                return f"Error: Starting search path '{target_path}' does not exist."
            if not target_path.is_dir():
                return f"Error: Search starting path '{target_path}' must be a directory."
            if not query:
                return "Error: No search query provided for search action."
                
            try:
                results = await asyncio.to_thread(_fast_search_sync, target_path, query)
                if not results:
                    return f"No items matching '{query}' were found under '{target_path}'."
                return "\n".join(results)
            except Exception as e:
                return f"Error searching under '{target_path}': {str(e)}"

        elif action == "delete":
            if not target_path.exists():
                return f"Error: File '{target_path}' does not exist."
            try:
                if target_path.is_file():
                    os.remove(target_path)
                    return f"Successfully deleted file '{target_path}'."
                elif target_path.is_dir():
                    return "Error: Path is a directory. Recursive directory deletion is restricted for safety."
                return f"Error: Path '{target_path}' could not be deleted (not a file)."
            except Exception as e:
                return f"Error deleting file '{target_path}': {str(e)}"

        else:
            return f"Error: Unsupported action '{action}'."
