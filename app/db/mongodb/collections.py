"""
MongoDB collection operations — chat history & document storage.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.db.mongodb.connection import get_mongo_db

#  CHAT HISTORY (Full unstructured conversation logs)

async def save_chat_message(
    session_id: str,
    role: str,           # "user" | "ceo" | "chro" | "regional_manager" | "mentor"
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Save a single chat message to MongoDB."""
    db = await get_mongo_db()
    doc = {
        "session_id": session_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
        "timestamp": datetime.utcnow(),
    }
    result = await db.chat_messages.insert_one(doc)
    return str(result.inserted_id)

async def get_chat_history(
    session_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve chat history for a session, ordered by time."""
    db = await get_mongo_db()
    cursor = (
        db.chat_messages
        .find({"session_id": session_id})
        .sort("timestamp", 1)
        .limit(limit)
    )
    messages = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        messages.append(doc)
    return messages

#  RESPONSE CACHE (Latency optimization)

async def get_cached_response(query_hash: str) -> Optional[str]:
    """Look up a cached LLM response by query hash."""
    db = await get_mongo_db()
    doc = await db.response_cache.find_one({"query_hash": query_hash})
    if doc:
        return doc["response"]
    return None

async def cache_response(query_hash: str, response: str, agent: str) -> None:
    """Cache an LLM response for future re-use."""
    db = await get_mongo_db()
    await db.response_cache.update_one(
        {"query_hash": query_hash},
        {
            "$set": {
                "response": response,
                "agent": agent,
                "cached_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )

#  RAW DOCUMENTS (Source PDF chunks — pre-ingestion backup)

async def store_document_chunk(
    chunk_text: str,
    source: str,
    role_access: List[str],
    topic: str,
    chunk_index: int,
) -> str:
    """Store a document chunk in MongoDB (backup of what goes into FAISS)."""
    db = await get_mongo_db()
    doc = {
        "text": chunk_text,
        "source": source,
        "role_access": role_access,     # ["CEO", "ALL"]
        "topic": topic,                  # "DNA", "competency_framework", etc.
        "chunk_index": chunk_index,
        "ingested_at": datetime.utcnow(),
    }
    result = await db.document_chunks.insert_one(doc)
    return str(result.inserted_id)
