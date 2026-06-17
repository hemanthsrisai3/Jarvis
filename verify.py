import os
import asyncio
import logging
import httpx
from config.settings import settings
from core.database import db_manager
from core.memory import vector_memory
from tools.registry import registry

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("jarvis.verification")

async def test_database():
    logger.info("--- Testing SQLite Database ---")
    try:
        await db_manager.initialize()
        await db_manager.clear_session("verify_session")
        await db_manager.add_message("verify_session", "user", "Verification ping")
        history = await db_manager.get_chat_history("verify_session")
        if len(history) > 0 and history[0]["content"] == "Verification ping":
            logger.info("✅ SQLite Database: SUCCESS (Write/Read matches)")
            await db_manager.clear_session("verify_session")
        else:
            logger.error("❌ SQLite Database: FAIL (Retrieval did not match)")
    except Exception as e:
        logger.error(f"❌ SQLite Database: FAIL ({e})")

async def test_tools():
    logger.info("--- Testing Tool Registry & Execution ---")
    registry.load_tools()
    tools = list(registry.tools.keys())
    logger.info(f"Loaded tools: {tools}")
    
    # 1. System stats tool
    try:
        res = await registry.execute_tool("system_stats", {})
        if "cpu" in res and "ram" in res:
            logger.info("✅ Tool [system_stats]: SUCCESS")
        else:
            logger.error(f"❌ Tool [system_stats]: FAIL (Unexpected response structure: {res[:100]})")
    except Exception as e:
        logger.error(f"❌ Tool [system_stats]: FAIL ({e})")

    # 2. Env stats tool
    try:
        res = await registry.execute_tool("env_stats", {})
        if "Time" in res and "Weather" in res:
            logger.info("✅ Tool [env_stats]: SUCCESS")
        else:
            logger.error(f"❌ Tool [env_stats]: FAIL (Unexpected response structure: {res[:100]})")
    except Exception as e:
        logger.error(f"❌ Tool [env_stats]: FAIL ({e})")

    # 3. File ops tool
    try:
        write_res = await registry.execute_tool("file_ops", {
            "action": "write", "path": "verify_test.txt", "content": "Jarvis verification token"
        })
        read_res = await registry.execute_tool("file_ops", {
            "action": "read", "path": "verify_test.txt"
        })
        list_res = await registry.execute_tool("file_ops", {
            "action": "list", "path": "."
        })
        delete_res = await registry.execute_tool("file_ops", {
            "action": "delete", "path": "verify_test.txt"
        })
        
        if "Success" in write_res and "verification token" in read_res and "verify_test.txt" in list_res and "deleted" in delete_res:
            logger.info("✅ Tool [file_ops]: SUCCESS (Sandboxed Write/Read/List/Delete)")
        else:
            logger.error(f"❌ Tool [file_ops]: FAIL (Operation pipeline check failed: write={write_res[:50]}, read={read_res[:50]})")
    except Exception as e:
        logger.error(f"❌ Tool [file_ops]: FAIL ({e})")

    # 4. Local browse tool
    try:
        res = await registry.execute_tool("local_browse", {"query": "Python Programming"})
        if "Title:" in res or "Snippet:" in res:
            logger.info("✅ Tool [local_browse]: SUCCESS")
        else:
            logger.error(f"❌ Tool [local_browse]: FAIL (Scraper structure check failed: {res[:100]})")
    except Exception as e:
        logger.error(f"❌ Tool [local_browse]: FAIL ({e})")

async def test_ollama():
    logger.info("--- Testing Ollama Integration ---")
    logger.info(f"Ollama Target URL: {settings.OLLAMA_BASE_URL}")
    
    # Check Ollama status
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(settings.OLLAMA_BASE_URL)
            if res.status_code == 200:
                logger.info("✅ Ollama Service: ONLINE")
            else:
                logger.warning(f"⚠️ Ollama Service: Warning (Returned code {res.status_code})")
    except Exception as e:
        logger.error(f"❌ Ollama Service: OFFLINE (Failed to connect to {settings.OLLAMA_BASE_URL}. Ensure Ollama is running.)")
        return

    # Check LLM model
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/show",
                json={"name": settings.LLM_MODEL}
            )
            if res.status_code == 200:
                logger.info(f"✅ Ollama LLM Model '{settings.LLM_MODEL}': AVAILABLE")
            else:
                logger.warning(f"⚠️ Ollama LLM Model '{settings.LLM_MODEL}': NOT FOUND. Pull with: ollama pull {settings.LLM_MODEL}")
    except Exception as e:
        logger.error(f"❌ Ollama LLM Model Check failed: {e}")

    # Check Embedding model
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/show",
                json={"name": settings.EMBEDDING_MODEL}
            )
            if res.status_code == 200:
                logger.info(f"✅ Ollama Embedding Model '{settings.EMBEDDING_MODEL}': AVAILABLE")
            else:
                logger.warning(f"⚠️ Ollama Embedding Model '{settings.EMBEDDING_MODEL}': NOT FOUND. Pull with: ollama pull {settings.EMBEDDING_MODEL}")
    except Exception as e:
        logger.error(f"❌ Ollama Embedding Model Check failed: {e}")

async def main():
    logger.info("=== J.A.R.V.I.S. VERIFICATION SUITE ===")
    await test_database()
    await test_tools()
    await test_ollama()
    logger.info("=== VERIFICATION PROCESS COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
