import json
import logging
import re
import time
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx
from config.settings import settings
from core.database import db_manager
from core.memory import vector_memory
from tools.registry import registry

logger = logging.getLogger("jarvis.agent")

SYSTEM_PROMPT = """You are J.A.R.V.I.S. (Just A Rather Very Intelligent System), a highly capable, efficient, articulate, and slightly witty digital assistant.
You are running completely locally on the user's host machine, utilizing hardware acceleration.
Your tone is professional, sophisticated, slightly formal, yet warm and loyal (reminiscent of Tony Stark's assistant).
You have full access to the host machine's entire file system across all drives (including the C:, D:, and E: drives) using absolute paths (e.g. 'D:\\some_folder\\file.txt'). Proactively use the 'file_ops' tool to list, search, read, write, or manage files on any drive requested by the user.
You can safely launch desktop applications (e.g. shorthand name like 'notepad', 'calculator', 'chrome', 'edge', 'paint', 'explorer', 'task manager' or a full path to an executable) using the 'app_launcher' tool. Proactively use this tool when the user asks you to open or run an application.
You can open the Windows system Clock app or schedule local alarms and timers in J.A.R.V.I.S. using the 'clock_app' tool. Proactively use it when the user asks you to open the clock, set an alarm, or set a timer.
Use your system tools proactively to fulfill the user's requests. If a tool fails or is unavailable, report the failure with sophistication and suggest alternatives.
Keep your responses concise, precise, and execute tasks cleanly. Address the user with respect."""

class JarvisAgent:
    """
    Orchestrates memory retrieval, Ollama chat request formatting,
    asynchronous tool execution loops, and response streaming.
    """
    def __init__(self) -> None:
        self.ollama_url = f"{settings.OLLAMA_BASE_URL}/api/chat"

    async def _detect_and_store_memory(self, user_input: str) -> None:
        """
        Heuristic to automatically extract and store important facts in vector memory.
        """
        input_lower = user_input.lower().strip()
        
        # Trigger conditions for memory saving
        memory_keywords = [
            "remember that", "remember this:", "note down that", "note that",
            "my favorite", "i prefer", "i use", "i work as", "i live in"
        ]
        
        should_remember = any(keyword in input_lower for keyword in memory_keywords)
        
        if should_remember:
            # Clean up the prefix if it starts with "remember that"
            text_to_save = user_input
            for kw in ["remember that", "remember this:", "note down that", "note that"]:
                if input_lower.startswith(kw):
                    text_to_save = user_input[len(kw):].strip()
                    break
            
            # Save to semantic vector database
            success = await vector_memory.add_memory(
                text=text_to_save,
                metadata={"source": "auto_extracted", "timestamp": str(datetime.now()) if 'datetime' in globals() else ""}
            )
            if success:
                logger.info(f"Auto-saved semantic fact: '{text_to_save}'")

    async def chat(self, session_id: str, user_input: str) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main orchestration loop:
        1. Inject semantic memory context.
        2. Format message history (short term).
        3. Call Ollama with tool schemas.
        4. Loop tool execution if the model requests it.
        5. Stream the final response to the user.
        """
        logger.info(f"Received chat request for session '{session_id}': '{user_input}'")

        # Automatically check and save facts in vector memory
        await self._detect_and_store_memory(user_input)

        # 1. Retrieve semantic memories from Vector DB
        relevant_memories = await vector_memory.search_memories(user_input, limit=3, threshold=0.45)
        memory_context = ""
        if relevant_memories:
            facts = "\n".join([f"- {m['text']}" for m in relevant_memories])
            memory_context = f"\n\n[System Context - Retained Memories of User]:\n{facts}"
            logger.info(f"Retrieved {len(relevant_memories)} semantic context items.")

        # 2. Build message list (System prompt + semantic context + SQLite history + current input)
        messages: List[Dict[str, Any]] = []
        
        # System prompt with injected memory context if present
        full_system_prompt = SYSTEM_PROMPT + memory_context
        messages.append({"role": "system", "content": full_system_prompt})

        # Load SQLite short-term conversation context (limit to last 6 messages)
        history = await db_manager.get_chat_history(session_id, limit=6)
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
            if "tool_calls" in msg and msg["tool_calls"]:
                messages[-1]["tool_calls"] = msg["tool_calls"]

        # Append current user prompt
        messages.append({"role": "user", "content": user_input})

        # Save user message to database
        await db_manager.add_message(session_id, "user", user_input)

        # 3. Retrieve Ollama-compatible tool schemas
        tool_schemas = registry.get_tool_definitions()

        # Http client for Ollama API requests
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Loop for handling multi-turn tool calling
            max_tool_loops = 5
            loop_count = 0
            
            while loop_count < max_tool_loops:
                logger.info(f"Sending request to Ollama (Loop {loop_count + 1})...")
                
                payload = {
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "num_ctx": 1024,
                        "temperature": 0.2,
                        "num_predict": 256
                    }
                }
                if tool_schemas:
                    payload["tools"] = tool_schemas

                accumulated_content = ""
                accumulated_tool_calls = []

                try:
                    async with client.stream("POST", self.ollama_url, json=payload) as response:
                        if response.status_code != 200:
                            err_content = await response.aread()
                            yield {"type": "error", "content": f"Ollama integration error: {err_content.decode('utf-8')}"}
                            return

                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = json.loads(line)
                                message_chunk = chunk.get("message", {})
                                
                                # Stream text content delta
                                content_chunk = message_chunk.get("content", "")
                                if content_chunk:
                                    accumulated_content += content_chunk
                                    yield {"type": "text", "content": content_chunk}
                                
                                # Gather tool calls
                                tool_calls_chunk = message_chunk.get("tool_calls", [])
                                if tool_calls_chunk:
                                    accumulated_tool_calls.extend(tool_calls_chunk)
                            except json.JSONDecodeError:
                                logger.error(f"Failed to parse SSE JSON line: {line}")
                except Exception as e:
                    logger.error(f"Ollama connection error during streaming: {e}")
                    yield {"type": "error", "content": f"Ollama connection error: {str(e)}"}
                    return

                # If no native tool calls, check if the model printed a JSON tool call block in the text
                if not accumulated_tool_calls:
                    text_clean = accumulated_content.strip()
                    # Balanced brace JSON extractor
                    block = None
                    start_idx = text_clean.find('{')
                    while start_idx != -1:
                        brace_count = 0
                        end_idx = -1
                        for i in range(start_idx, len(text_clean)):
                            char = text_clean[i]
                            if char == '{':
                                brace_count += 1
                            elif char == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    end_idx = i
                                    break
                        if end_idx != -1:
                            sub_block = text_clean[start_idx:end_idx+1]
                            if "name" in sub_block:
                                block = sub_block
                                break
                        start_idx = text_clean.find('{', start_idx + 1)

                    if block:
                        data = None
                        try:
                            data = json.loads(block)
                        except Exception:
                            # Fallback: parse single quotes or Python dict format using ast.literal_eval
                            import ast
                            try:
                                parsed = ast.literal_eval(block)
                                if isinstance(parsed, dict):
                                    data = parsed
                            except Exception as eval_err:
                                logger.debug(f"ast.literal_eval fallback failed: {eval_err}")

                        if data and isinstance(data, dict):
                            name = data.get("name")
                            arguments = data.get("arguments") or data.get("args") or data.get("parameters") or {}
                            if isinstance(arguments, str):
                                try:
                                    arguments = json.loads(arguments)
                                except Exception:
                                    import ast
                                    try:
                                        arguments = ast.literal_eval(arguments)
                                    except Exception:
                                        arguments = {}
                            if name:
                                logger.info(f"Failsafe parser detected raw text tool call for '{name}': {arguments}")
                                accumulated_tool_calls = [{
                                    "id": f"text_call_{int(time.time())}",
                                    "type": "function",
                                    "function": {
                                        "name": name,
                                        "arguments": arguments
                                    }
                                }]

                # If no tool calls are requested (either native or parsed), we break and finish
                if not accumulated_tool_calls:
                    # Save response to SQLite database
                    await db_manager.add_message(session_id, "assistant", accumulated_content)
                    return

                # Save assistant message containing tool calls to conversation history
                assistant_msg = {
                    "role": "assistant",
                    "content": accumulated_content,
                    "tool_calls": accumulated_tool_calls
                }
                messages.append(assistant_msg)
                await db_manager.add_message(
                    session_id=session_id,
                    role="assistant",
                    content=accumulated_content,
                    tool_calls=accumulated_tool_calls
                )

                # Process all tool calls requested in this turn
                for tool_call in accumulated_tool_calls:
                    function_info = tool_call.get("function", {})
                    tool_name = function_info.get("name")
                    tool_args = function_info.get("arguments", {})

                    # Notify frontend that a tool execution is starting
                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "arguments": tool_args
                    }

                    # Execute tool asynchronously
                    tool_result = await registry.execute_tool(tool_name, tool_args)

                    # Notify frontend of tool output
                    yield {
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "result": tool_result
                    }

                    # Append tool result to messages history for the next Ollama prompt
                    tool_message = {
                        "role": "tool",
                        "name": tool_name,
                        "content": tool_result
                    }
                    messages.append(tool_message)

                loop_count += 1

            # If tool loops exceed threshold, output warning
            warning_msg = "Error: Tool execution loop limit exceeded. Halting loop to prevent system cascade."
            yield {"type": "error", "content": warning_msg}
            await db_manager.add_message(session_id, "assistant", warning_msg)

# Shared instance
jarvis_agent = JarvisAgent()
