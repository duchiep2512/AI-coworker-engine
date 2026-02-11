"""
FastAPI dependency injection.
"""

from app.db.postgres.connection import get_db

# Re-export for clean imports in route files
__all__ = ["get_db"]
