"""
Pydantic schemas for agent/persona configuration.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

class PersonaConfig(BaseModel):
    """Configuration for a single AI Co-worker persona."""

    agent_id: str = Field(..., description="Unique agent key: CEO, CHRO, RegionalManager")
    display_name: str = Field(..., description="Human-readable name shown in UI")
    role_title: str = Field(..., description="Job title within the simulation")
    personality_traits: List[str] = Field(default_factory=list)
    hidden_constraints: List[str] = Field(
        default_factory=list,
        description="Constraints invisible to user but shape agent behavior",
    )
    knowledge_scope: List[str] = Field(
        default_factory=list,
        description="Topics this agent is authorized to discuss",
    )
    tools: List[str] = Field(
        default_factory=list,
        description="Tools available to this agent (e.g., kpi_calculator)",
    )

class AgentStatusResponse(BaseModel):
    """Status of a specific agent in current session."""
    agent_id: str
    is_active: bool
    interaction_count: int
    last_sentiment: Optional[str] = None
