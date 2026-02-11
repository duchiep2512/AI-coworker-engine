"""
Session management endpoints.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.post("/start")
async def start_session(user_id: str, simulation_id: str = "gucci_2.0"):
    """
    Start a new simulation session.
    In production, this creates a PostgreSQL session record.
    For the prototype, we use in-memory state.
    """
    import uuid
    session_id = str(uuid.uuid4())

    return {
        "session_id": session_id,
        "user_id": user_id,
        "simulation_id": simulation_id,
        "status": "active",
        "message": "Simulation started. You can now chat with AI co-workers.",
    }

@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get current session state."""
    return {
        "session_id": session_id,
        "status": "active",
        "message": "Session state retrieval — connect to PostgreSQL in production.",
    }
