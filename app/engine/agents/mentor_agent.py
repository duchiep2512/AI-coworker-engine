"""
Mentor Agent — HRM Learning Mentor node.
Provides helpful hints and guidance to the simulation taker.
"""

from app.engine.agents.base_agent import BaseNPCAgent
from app.engine.state import AgentState
from app.personas.prompts import MENTOR_PROMPT

class MentorAgent(BaseNPCAgent):
    agent_id = "Mentor"
    fallback_prompt = MENTOR_PROMPT  # Used if PostgreSQL unavailable

_agent = MentorAgent()

def mentor_node(state: AgentState) -> dict:
    """LangGraph node function for the Mentor agent."""
    result = _agent.invoke(state)
    return result
