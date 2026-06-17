import os
import json
import logging
from typing import List, Dict, Any, Optional
import httpx
import numpy as np
from config.settings import settings

logger = logging.getLogger("jarvis.memory")

class VectorMemory:
    """
    Saves and retrieves semantic context using local JSON storage and Ollama embeddings.
    """
    def __init__(self, db_path: str = str(settings.VECTOR_DB_PATH)):
        self.db_path = db_path
        self.memories: List[Dict[str, Any]] = []
        self._load_memories()
        self.embeddings_supported = True

    def _load_memories(self) -> None:
        """
        Load memories from the local file system.
        """
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
                logger.info(f"Loaded {len(self.memories)} memories from {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")
                self.memories = []
        else:
            self.memories = []

    def _save_memories(self) -> None:
        """
        Save memories back to the local file system.
        """
        try:
            # Create directories if needed
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding vector for the given text using Ollama's local embedding API.
        Attempts both newer /api/embed and older /api/embeddings endpoints for compatibility.
        """
        if not self.embeddings_supported:
            return None

        headers = {"Content-Type": "application/json"}
        
        # Method 1: Try new /api/embed endpoint
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embed",
                    json={"model": settings.EMBEDDING_MODEL, "input": text},
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    if "embeddings" in data and len(data["embeddings"]) > 0:
                        return data["embeddings"][0]
                elif response.status_code == 501 or (response.status_code == 500 and "does not support embeddings" in response.text):
                    logger.warning("Ollama server or model does not support embeddings. Disabling vector memory search.")
                    self.embeddings_supported = False
                    return None
        except Exception as e:
            logger.debug(f"Ollama /api/embed endpoint failed, trying fallback: {e}")

        # Method 2: Try older /api/embeddings endpoint fallback
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/embeddings",
                    json={"model": settings.EMBEDDING_MODEL, "prompt": text},
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    if "embedding" in data:
                        return data["embedding"]
                elif response.status_code == 501 or (response.status_code == 500 and "does not support embeddings" in response.text):
                    logger.warning("Ollama server or model does not support embeddings. Disabling vector memory search.")
                    self.embeddings_supported = False
                    return None
        except Exception as e:
            logger.error(f"Ollama embedding generation failed entirely: {e}")
        
        return None

    async def add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Generate an embedding and store the memory.
        """
        if not text.strip():
            return False

        logger.info(f"Adding semantic memory: '{text[:50]}...'")
        vector = await self.get_embedding(text)
        if vector is None:
            logger.warning("Could not generate embedding for memory. Memory not saved.")
            return False

        self.memories.append({
            "text": text,
            "vector": vector,
            "metadata": metadata or {}
        })
        self._save_memories()
        return True

    async def search_memories(self, query: str, limit: int = 3, threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Perform cosine similarity search across stored memories.
        """
        if not self.memories or not query.strip():
            return []

        query_vector = await self.get_embedding(query)
        if query_vector is None:
            logger.warning("Could not generate query embedding. Returning empty search results.")
            return []

        q_vec = np.array(query_vector)
        q_norm = np.linalg.norm(q_vec)
        
        if q_norm == 0:
            return []

        results = []
        for memory in self.memories:
            m_vec = np.array(memory["vector"])
            m_norm = np.linalg.norm(m_vec)
            
            if m_norm == 0:
                continue
                
            # Compute cosine similarity
            similarity = float(np.dot(q_vec, m_vec) / (q_norm * m_norm))
            
            if similarity >= threshold:
                results.append({
                    "text": memory["text"],
                    "metadata": memory["metadata"],
                    "similarity": similarity
                })

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:limit]

    def clear_all(self) -> None:
        """
        Clear all vector memories.
        """
        self.memories = []
        self._save_memories()

# Shared instance
vector_memory = VectorMemory()
