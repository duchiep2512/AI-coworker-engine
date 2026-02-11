"""
Pydantic schemas for Chat API request/response.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

#  REQUEST

class ChatRequest(BaseModel):
    """Incoming chat message from the simulation taker."""

    user_id: str = Field(..., description="Unique user identifier")
    session_id: Optional[str] = Field(None, description="Existing session ID (auto-created if None)")
    message: str = Field(..., min_length=1, max_length=2000, description="User's message text")
    target_agent: Optional[str] = Field(
        None,
        description="Optionally address a specific co-worker: CEO, CHRO, RegionalManager",
    )

    model_config = {"json_schema_extra": {
        "examples": [{
            "user_id": "user_001",
            "message": "How do we balance group standardization with brand autonomy?",
            "target_agent": "CEO",
        }]
    }}

#  RESPONSE

class SafetyFlags(BaseModel):
    """Safety analysis of the interaction."""
    is_safe: bool = True
    blocked_reason: Optional[str] = None
    jailbreak_attempt: bool = False
    off_topic: bool = False

class StateUpdate(BaseModel):
    """State changes after this interaction turn."""
    current_speaker: str
    sentiment_score: float = Field(ge=0.0, le=1.0)
    turn_count: int
    task_progress: Dict[str, Any] = {}
    hint_triggered: bool = False

class ChatResponse(BaseModel):
    """Response from the AI Co-worker Engine."""

    session_id: str
    agent: str = Field(..., description="Which co-worker responded (CEO, CHRO, RegionalManager, Mentor)")
    response: str = Field(..., description="The AI co-worker's message")
    state_update: StateUpdate
    safety_flags: SafetyFlags
    latency_ms: int = Field(..., description="Response time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"json_schema_extra": {
        "examples": [{
            "session_id": "abc-123",
            "agent": "CEO",
            "response": "Great question. At Gucci Group, we believe brand autonomy is sacred...",
            "state_update": {
                "current_speaker": "CEO",
                "sentiment_score": 0.8,
                "turn_count": 3,
                "task_progress": {"ceo_consulted": True},
                "hint_triggered": False,
            },
            "safety_flags": {"is_safe": True, "jailbreak_attempt": False, "off_topic": False},
            "latency_ms": 1200,
        }]
    }}

#  CHAT HISTORY

class ChatMessage(BaseModel):
    """Single message in chat history."""
    role: str
    content: str
    timestamp: datetime

class ChatHistoryResponse(BaseModel):
    """Full chat history for a session."""
    session_id: str
    messages: List[ChatMessage]
    total: int
