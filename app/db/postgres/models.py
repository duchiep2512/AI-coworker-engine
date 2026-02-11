"""
PostgreSQL ORM Models — structured data.
Tables: users, simulation_sessions, task_progress
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.postgres.connection import Base

class User(Base):
    """Simulation taker profile."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship("SimulationSession", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username}>"

class SimulationSession(Base):
    """One simulation run (e.g. a user doing the Gucci 2.0 sim)."""

    __tablename__ = "simulation_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    simulation_id = Column(String(100), nullable=False, default="gucci_2.0")
    status = Column(String(20), default="active")  # active | completed | abandoned

    # State snapshot (serialized AgentState)
    current_speaker = Column(String(50), default="supervisor")
    sentiment_score = Column(Float, default=0.5)  # 0.0 = frustrated, 1.0 = confident
    turn_count = Column(Integer, default=0)

    # Task progress (JSON blob — flat dict matching state.py DEFAULT_TASK_PROGRESS)
    task_progress = Column(JSON, default=lambda: {
        "problem_statement_written": False,
        "ceo_consulted": False,
        "chro_consulted": False,
        "competency_model_drafted": False,
        "360_program_designed": False,
        "regional_manager_consulted": False,
        "rollout_plan_built": False,
        "kpi_table_defined": False,
    })

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")

    def __repr__(self):
        return f"<Session {self.id} user={self.user_id} status={self.status}>"

class AgentInteractionLog(Base):
    """Structured log of each agent interaction (for analytics)."""

    __tablename__ = "agent_interaction_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("simulation_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    agent_name = Column(String(50), nullable=False)  # CEO, CHRO, RegionalManager, Mentor
    user_intent = Column(String(100), nullable=True)  # Classified intent
    sentiment = Column(String(20), nullable=True)  # positive, neutral, confused, frustrated
    hint_triggered = Column(Boolean, default=False)
    safety_flag = Column(Boolean, default=False)
    latency_ms = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Interaction turn={self.turn_number} agent={self.agent_name}>"

class Agent(Base):
    """
    NPC Agent definitions — stores persona/system prompts in PostgreSQL.
    This allows dynamic persona updates without code changes.
    """

    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False, index=True)  # CEO, CHRO, RegionalManager
    display_name = Column(String(100), nullable=False)  # "Gucci Group CEO"
    role_description = Column(Text, nullable=False)  # Short description
    simulation_id = Column(String(100), default="gucci_2.0")
    
    # The core system prompt (persona definition)
    system_prompt = Column(Text, nullable=False)
    
    # Behavioral parameters
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=512)
    
    # Topics this agent is expert in
    expertise_topics = Column(JSON, default=list)  # ["brand_dna", "strategy", "leadership"]
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Agent {self.name} ({self.display_name})>"

class Simulation(Base):
    """Simulation/Case study definitions."""

    __tablename__ = "simulations"

    id = Column(String(100), primary_key=True)  # gucci_2.0
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Simulation {self.id}: {self.title}>"
