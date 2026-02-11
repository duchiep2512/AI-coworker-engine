"""
Agent Loader — Fetch agent configs from PostgreSQL with fallback to hardcoded prompts.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass

from app.core.logging import logger

@dataclass
class AgentConfig:
    """Agent configuration loaded from database or fallback."""
    name: str
    display_name: str
    role_description: str
    system_prompt: str
    temperature: float = 0.7
    max_tokens: int = 512
    expertise_topics: list = None
    
    def __post_init__(self):
        if self.expertise_topics is None:
            self.expertise_topics = []

# Cache for loaded agents (to avoid repeated DB calls during a session)
_agent_cache: Dict[str, AgentConfig] = {}

async def get_agent_config(agent_name: str) -> AgentConfig:
    """
    Load agent configuration.
    Priority: PostgreSQL → Hardcoded fallback
    """
    # Check cache first
    if agent_name in _agent_cache:
        return _agent_cache[agent_name]
    
    # Try loading from PostgreSQL
    config = await _load_from_postgres(agent_name)
    
    if config is None:
        # Fallback to hardcoded prompts
        config = _load_from_hardcoded(agent_name)
        logger.debug(f"Agent {agent_name} loaded from hardcoded prompts (fallback)")
    else:
        logger.debug(f"Agent {agent_name} loaded from PostgreSQL")
    
    # Cache it
    if config:
        _agent_cache[agent_name] = config
    
    return config

async def _load_from_postgres(agent_name: str) -> Optional[AgentConfig]:
    """Attempt to load agent from PostgreSQL."""
    try:
        from app.db.postgres.connection import AsyncSessionLocal
        from app.db.postgres.crud import get_agent_by_name
        
        async with AsyncSessionLocal() as db:
            agent = await get_agent_by_name(db, agent_name)
            if agent:
                return AgentConfig(
                    name=agent.name,
                    display_name=agent.display_name,
                    role_description=agent.role_description,
                    system_prompt=agent.system_prompt,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                    expertise_topics=agent.expertise_topics or [],
                )
    except Exception as e:
        logger.warning(f"Could not load agent {agent_name} from PostgreSQL: {e}")
    
    return None

def _load_from_hardcoded(agent_name: str) -> Optional[AgentConfig]:
    """Load agent from hardcoded prompts.py (fallback)."""
    from app.personas.prompts import CEO_PROMPT, CHRO_PROMPT, REGIONAL_MANAGER_PROMPT, MENTOR_PROMPT
    
    prompts_map = {
        "CEO": {
            "display_name": "Gucci Group CEO",
            "role_description": "CEO of Gucci Group — strategic visionary",
            "system_prompt": CEO_PROMPT,
            "expertise_topics": ["brand_dna", "strategy", "leadership", "vision"],
        },
        "CHRO": {
            "display_name": "Gucci Group CHRO",
            "role_description": "Chief Human Resources Officer — HR expert",
            "system_prompt": CHRO_PROMPT,
            "expertise_topics": ["hr", "talent", "competency", "development"],
        },
        "RegionalManager": {
            "display_name": "Europe Regional Manager",
            "role_description": "Regional Manager for Europe — Employer Branding & Internal Communications",
            "system_prompt": REGIONAL_MANAGER_PROMPT,
            "expertise_topics": ["operations", "regional", "europe", "implementation", "rollout"],
        },
        "Mentor": {
            "display_name": "HRM Learning Mentor",
            "role_description": "Your helpful mentor — provides hints and guidance",
            "system_prompt": MENTOR_PROMPT,
            "expertise_topics": ["learning", "hints", "guidance", "help"],
        },
    }
    
    if agent_name in prompts_map:
        data = prompts_map[agent_name]
        return AgentConfig(
            name=agent_name,
            display_name=data["display_name"],
            role_description=data["role_description"],
            system_prompt=data["system_prompt"],
            expertise_topics=data["expertise_topics"],
        )
    
    return None

def clear_agent_cache():
    """Clear the agent cache (useful for testing or hot-reload)."""
    _agent_cache.clear()

async def get_system_prompt(agent_name: str) -> str:
    """Convenience method: get just the system prompt for an agent."""
    config = await get_agent_config(agent_name)
    if config:
        return config.system_prompt
    return ""
