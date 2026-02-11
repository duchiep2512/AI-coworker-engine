"""
Seed PostgreSQL with initial Agent and Simulation data.
Run this on startup to ensure agents exist in the database.
"""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.db.postgres.models import Agent, Simulation
from app.personas.prompts import (
    CEO_PROMPT, CHRO_PROMPT, REGIONAL_MANAGER_PROMPT, MENTOR_PROMPT,
)

#  SEED DATA (prompts imported from prompts.py)

AGENTS_SEED_DATA = [
    {
        "name": "CEO",
        "display_name": "Gucci Group CEO",
        "role_description": "Chief Executive Officer — Group DNA & Strategy",
        "simulation_id": "gucci_2.0",
        "system_prompt": CEO_PROMPT,
        "temperature": 0.7,
        "max_tokens": 512,
        "expertise_topics": ["brand_dna", "strategy", "leadership", "autonomy", "craftsmanship"],
    },
    {
        "name": "CHRO",
        "display_name": "Gucci Group CHRO",
        "role_description": "Chief Human Resources Officer — HR & Competencies",
        "simulation_id": "gucci_2.0",
        "system_prompt": CHRO_PROMPT,
        "temperature": 0.6,
        "max_tokens": 600,
        "expertise_topics": ["hr", "competency_framework", "360_feedback", "coaching", "talent_development"],
    },
    {
        "name": "RegionalManager",
        "display_name": "Europe Regional Manager",
        "role_description": "Employer Branding & Internal Communications — Europe Operations",
        "simulation_id": "gucci_2.0",
        "system_prompt": REGIONAL_MANAGER_PROMPT,
        "temperature": 0.65,
        "max_tokens": 450,
        "expertise_topics": ["rollout", "regional", "europe", "training", "implementation"],
    },
    {
        "name": "Mentor",
        "display_name": "Simulation Mentor",
        "role_description": "Learning Guide — Hints & Guidance",
        "simulation_id": "gucci_2.0",
        "system_prompt": MENTOR_PROMPT,
        "temperature": 0.5,
        "max_tokens": 256,
        "expertise_topics": ["guidance", "hints", "help"],
    },
]

SIMULATIONS_SEED_DATA = [
    {
        "id": "gucci_2.0",
        "title": "Gucci Group — HRM Talent & Leadership Development 2.0",
        "description": "Design a leadership development program balancing Group DNA with brand autonomy across 9 luxury brands.",
        "thumbnail_url": None,
        "is_active": True,
    },
]

#  SEEDING FUNCTIONS

async def seed_simulations(db: AsyncSession) -> None:
    """Seed simulation definitions."""
    for sim_data in SIMULATIONS_SEED_DATA:
        existing = await db.execute(
            select(Simulation).where(Simulation.id == sim_data["id"])
        )
        if existing.scalar_one_or_none() is None:
            sim = Simulation(**sim_data)
            db.add(sim)
            logger.info(f"Seeded simulation: {sim_data['id']}")
    await db.commit()

async def seed_agents(db: AsyncSession) -> None:
    """Seed agent definitions with system prompts."""
    for agent_data in AGENTS_SEED_DATA:
        result = await db.execute(
            select(Agent).where(Agent.name == agent_data["name"])
        )
        existing_agent = result.scalar_one_or_none()
        
        if existing_agent is None:
            agent = Agent(**agent_data)
            db.add(agent)
            logger.info(f"Seeded agent: {agent_data['name']}")
        else:
            # Always sync prompt from prompts.py → DB on startup
            existing_agent.system_prompt = agent_data["system_prompt"]
            existing_agent.updated_at = datetime.utcnow()
            logger.info(f"Synced prompt: {agent_data['name']}")
    await db.commit()
    
    # Clear agent cache so new prompts take effect immediately
    try:
        from app.db.agent_loader import clear_agent_cache
        clear_agent_cache()
        logger.info("Agent cache cleared after seeding")
    except Exception:
        pass

async def seed_all(db: AsyncSession) -> None:
    """Run all seed functions."""
    await seed_simulations(db)
    await seed_agents(db)
    logger.info("Database seeding complete")
