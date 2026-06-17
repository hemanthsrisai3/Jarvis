import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import aiosqlite
from config.settings import settings

logger = logging.getLogger("jarvis.database")

class DatabaseManager:
    """
    Manages SQLite database operations for chat history and session persistence.
    """
    def __init__(self, db_path: str = str(settings.DATABASE_PATH)):
        self.db_path = db_path

    async def initialize(self) -> None:
        """
        Initialize SQLite tables if they do not exist.
        """
        logger.info(f"Initializing database at {self.db_path}")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT NOT NULL,
                    content TEXT,
                    tool_calls TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            await db.commit()

    async def create_session(self, session_id: str) -> str:
        """
        Create a new chat session if it does not exist.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO sessions (session_id) VALUES (?)",
                (session_id,)
            )
            await db.commit()
            return session_id

    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: Optional[str], 
        tool_calls: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Add a message to a session history.
        """
        # Ensure session exists first
        await self.create_session(session_id)
        
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO messages (session_id, role, content, tool_calls) VALUES (?, ?, ?, ?)",
                (session_id, role, content, tool_calls_json)
            )
            await db.execute(
                "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                (session_id,)
            )
            await db.commit()

    async def get_chat_history(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Retrieve the message history for a specific session.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT role, content, tool_calls, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
                (session_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                history = []
                for row in rows:
                    msg = {
                        "role": row["role"],
                        "content": row["content"],
                        "timestamp": row["timestamp"]
                    }
                    if row["tool_calls"]:
                        msg["tool_calls"] = json.loads(row["tool_calls"])
                    history.append(msg)
                return history

    async def clear_session(self, session_id: str) -> None:
        """
        Delete all messages for a session.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            await db.commit()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all active sessions sorted by last active time.
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT session_id, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

# Shared instance
db_manager = DatabaseManager()
