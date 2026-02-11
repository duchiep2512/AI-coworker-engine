"""
PostgreSQL CRUD operations for sessions, agents, and interaction logs.
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres.models import User, SimulationSession, AgentInteractionLog, Agent, Simulation

#  USER

async def get_or_create_user(db: AsyncSession, username: str) -> User:
    """Get existing user or create a new one."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(username=username)
        db.add(user)
        await db.flush()
    return user

#  SIMULATION SESSION

async def create_session(db: AsyncSession, user_id: uuid.UUID, simulation_id: str = "gucci_2.0") -> SimulationSession:
    """Start a new simulation session."""
    session = SimulationSession(user_id=user_id, simulation_id=simulation_id)
    db.add(session)
    await db.flush()
    return session

async def get_active_session(db: AsyncSession, user_id: uuid.UUID) -> Optional[SimulationSession]:
    """Get the user's currently active session."""
    result = await db.execute(
        select(SimulationSession)
        .where(SimulationSession.user_id == user_id, SimulationSession.status == "active")
        .order_by(SimulationSession.started_at.desc())
    )
    return result.scalar_one_or_none()

async def update_session_state(
    db: AsyncSession,
    session_id: uuid.UUID,
    current_speaker: Optional[str] = None,
    sentiment_score: Optional[float] = None,
    turn_count: Optional[int] = None,
    task_progress: Optional[dict] = None,
) -> None:
    """Update session state after each interaction turn."""
    values = {}
    if current_speaker is not None:
        values["current_speaker"] = current_speaker
    if sentiment_score is not None:
        values["sentiment_score"] = sentiment_score
    if turn_count is not None:
        values["turn_count"] = turn_count
    if task_progress is not None:
        values["task_progress"] = task_progress

    if values:
        await db.execute(
            update(SimulationSession)
            .where(SimulationSession.id == session_id)
            .values(**values)
        )

async def end_session(db: AsyncSession, session_id: uuid.UUID) -> None:
    """Mark a session as completed."""
    await db.execute(
        update(SimulationSession)
        .where(SimulationSession.id == session_id)
        .values(status="completed", ended_at=datetime.utcnow())
    )

#  INTERACTION LOG

async def log_interaction(
    db: AsyncSession,
    session_id: uuid.UUID,
    turn_number: int,
    agent_name: str,
    user_intent: Optional[str] = None,
    sentiment: Optional[str] = None,
    hint_triggered: bool = False,
    safety_flag: bool = False,
    latency_ms: Optional[int] = None,
) -> AgentInteractionLog:
    """Record one agent interaction for analytics."""
    log = AgentInteractionLog(
        session_id=session_id,
        turn_number=turn_number,
        agent_name=agent_name,
        user_intent=user_intent,
        sentiment=sentiment,
        hint_triggered=hint_triggered,
        safety_flag=safety_flag,
        latency_ms=latency_ms,
    )
    db.add(log)
    await db.flush()
    return log

#  AGENT

async def get_agent_by_name(db: AsyncSession, name: str) -> Optional[Agent]:
    """Get an agent by its name (CEO, CHRO, RegionalManager, Mentor)."""
    result = await db.execute(
        select(Agent).where(Agent.name == name, Agent.is_active == True)
    )
    return result.scalar_one_or_none()

async def get_all_agents(db: AsyncSession, simulation_id: str = "gucci_2.0") -> List[Agent]:
    """Get all active agents for a simulation."""
    result = await db.execute(
        select(Agent)
        .where(Agent.simulation_id == simulation_id, Agent.is_active == True)
        .order_by(Agent.name)
    )
    return list(result.scalars().all())

async def get_agent_prompt(db: AsyncSession, name: str) -> Optional[str]:
    """Get just the system prompt for an agent."""
    agent = await get_agent_by_name(db, name)
    return agent.system_prompt if agent else None

async def create_or_update_agent(
    db: AsyncSession,
    name: str,
    display_name: str,
    role_description: str,
    system_prompt: str,
    simulation_id: str = "gucci_2.0",
    temperature: float = 0.7,
    max_tokens: int = 512,
    expertise_topics: Optional[List[str]] = None,
) -> Agent:
    """Create a new agent or update if exists."""
    existing = await get_agent_by_name(db, name)
    if existing:
        existing.display_name = display_name
        existing.role_description = role_description
        existing.system_prompt = system_prompt
        existing.temperature = temperature
        existing.max_tokens = max_tokens
        existing.expertise_topics = expertise_topics or []
        await db.flush()
        return existing
    else:
        agent = Agent(
            name=name,
            display_name=display_name,
            role_description=role_description,
            system_prompt=system_prompt,
            simulation_id=simulation_id,
            temperature=temperature,
            max_tokens=max_tokens,
            expertise_topics=expertise_topics or [],
        )
        db.add(agent)
        await db.flush()
        return agent

#  SIMULATION

async def get_simulation(db: AsyncSession, simulation_id: str) -> Optional[Simulation]:
    """Get a simulation by ID."""
    result = await db.execute(
        select(Simulation).where(Simulation.id == simulation_id, Simulation.is_active == True)
    )
    return result.scalar_one_or_none()

async def create_or_update_simulation(
    db: AsyncSession,
    simulation_id: str,
    title: str,
    description: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
) -> Simulation:
    """Create or update a simulation."""
    existing = await get_simulation(db, simulation_id)
    if existing:
        existing.title = title
        existing.description = description
        existing.thumbnail_url = thumbnail_url
        await db.flush()
        return existing
    else:
        sim = Simulation(
            id=simulation_id,
            title=title,
            description=description,
            thumbnail_url=thumbnail_url,
        )
        db.add(sim)
        await db.flush()
        return sim
