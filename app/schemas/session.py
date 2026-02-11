"""
Pydantic schemas for session management.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

class SessionCreate(BaseModel):
    """Request to start a new simulation session."""
    user_id: str
    simulation_id: str = "gucci_2.0"

class SessionResponse(BaseModel):
    """Session state returned to the frontend."""
    session_id: str
    user_id: str
    simulation_id: str
    status: str
    current_speaker: str
    sentiment_score: float
    turn_count: int
    task_progress: Dict[str, Any]
    started_at: datetime
    ended_at: Optional[datetime] = None

class SessionEndRequest(BaseModel):
    """Request to end/complete a session."""
    session_id: str
    reason: str = Field(default="completed", description="completed | abandoned")
