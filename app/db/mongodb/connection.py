"""
MongoDB connection — async client via Motor.
Stores: Full chat logs (unstructured), raw document chunks, cached responses.
"""

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

async def get_mongo_db() -> AsyncIOMotorDatabase:
    """Return the MongoDB database instance (creates client on first call)."""
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
        _db = _client[settings.MONGO_DB]
        logger.info(f"MongoDB connected → {settings.MONGO_DB}")
    return _db

async def close_mongo():
    """Close MongoDB client on shutdown."""
    global _client
    if _client:
        _client.close()
        _client = None
        logger.info("MongoDB connection closed")
