import logging
import json
from typing import Dict, Any
from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from core.database import db_manager
from core.agent import jarvis_agent
from tools.registry import registry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("jarvis.core")

app = FastAPI(
    title="J.A.R.V.I.S. Core Engine",
    description="Asynchronous local AI assistant core handles tools and orchestration.",
    version="1.0.0"
)

# Enable CORS for local developments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    """
    Setup databases and preload tools on application startup.
    """
    logger.info("Starting J.A.R.V.I.S. Core Service...")
    await db_manager.initialize()
    logger.info("J.A.R.V.I.S. Database initialized successfully.")

@app.get("/api/health")
async def health_check():
    """
    Verification and diagnostic endpoint.
    """
    return {
        "status": "online",
        "llm_model": settings.LLM_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL,
        "ollama_url": settings.OLLAMA_BASE_URL,
        "tools_loaded": list(registry.tools.keys())
    }

@app.get("/api/sessions")
async def get_sessions():
    """
    Retrieve list of active chat sessions.
    """
    try:
        sessions = await db_manager.list_sessions()
        return {"status": "success", "sessions": sessions}
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
async def get_history(session_id: str = Query(..., description="The session ID to retrieve logs for")):
    """
    Retrieve message history for a specific session.
    """
    try:
        history = await db_manager.get_chat_history(session_id)
        return {"status": "success", "session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Error fetching history for session '{session_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/clear")
async def clear_session(payload: Dict[str, str] = Body(...)):
    """
    Delete chat logs for a given session.
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id in request body.")
    try:
        await db_manager.clear_session(session_id)
        return {"status": "success", "message": f"Session '{session_id}' cleared."}
    except Exception as e:
        logger.error(f"Error clearing session '{session_id}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_endpoint(payload: Dict[str, Any] = Body(...)):
    """
    Chat endpoint returns a Server-Sent Events stream:
    - yields text chunks as they compile
    - yields tool execution start and end logs in real-time
    """
    session_id = payload.get("session_id")
    message = payload.get("message")

    if not session_id or not message:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain 'session_id' and 'message'."
        )

    async def sse_generator():
        try:
            async for event in jarvis_agent.chat(session_id, message):
                # Standard Server-Sent Events format
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(f"SSE Chat loop exception: {e}", exc_info=True)
            err_event = {"type": "error", "content": f"Streaming system error: {str(e)}"}
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.get("/api/system-stats")
async def get_system_stats():
    """
    Get basic host system resource stats for the dashboard sidebar meters and check for fired alerts.
    """
    import psutil
    import time
    from tools.clock_manager import get_fired_alerts, get_active_alerts
    try:
        # non-blocking CPU check
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        try:
            disk = psutil.disk_usage("/").percent
        except Exception:
            disk = psutil.disk_usage(".").percent
        
        fired = get_fired_alerts()
        active = [{
            "id": a["id"],
            "type": a["type"],
            "label": a["label"],
            "target_time": a["target_time"],
            "remaining": max(0, int(a["target_time"] - time.time()))
        } for a in get_active_alerts()]
        
        return {
            "cpu": cpu,
            "ram": ram,
            "disk": disk,
            "alerts": fired,
            "active_alerts": active
        }
    except Exception as e:
        logger.error(f"Error fetching system stats for endpoint: {e}")
        return {"cpu": 0, "ram": 0, "disk": 0, "alerts": [], "active_alerts": [], "error": str(e)}

@app.post("/api/cancel-alert")
async def cancel_alert_endpoint(payload: Dict[str, str] = Body(...)):
    """
    Endpoint to cancel a pending alert by ID.
    """
    from tools.clock_manager import cancel_alert
    alert_id = payload.get("id")
    if not alert_id:
        raise HTTPException(status_code=400, detail="Missing alert ID 'id' in payload.")
    
    success = cancel_alert(alert_id)
    if success:
        return {"status": "success", "message": f"Alert '{alert_id}' cancelled."}
    else:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found or already fired.")

@app.get("/api/tts")
async def text_to_speech(text: str = Query(..., description="Text to convert to speech")):
    """
    Generate premium neural audio for text using edge-tts (RyanNeural).
    """
    import edge_tts
    voice = "en-GB-RyanNeural"
    try:
        communicate = edge_tts.Communicate(text, voice)
        async def audio_generator():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        return StreamingResponse(audio_generator(), media_type="audio/mpeg")
    except Exception as e:
        logger.error(f"Error generating neural TTS: {e}")
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {str(e)}")

# Mount Static UI Folder (Serves index.html at root "/")
app.mount("/", StaticFiles(directory="core/static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("core.main:app", host=settings.API_HOST, port=settings.API_PORT, reload=True)
