"""
CHRO Agent — Gucci Group Chief Human Resources Officer node.
Guides competency framework, 360° feedback, and talent development.
"""

from app.engine.agents.base_agent import BaseNPCAgent
from app.engine.state import AgentState, update_agent_emotion
from app.personas.prompts import CHRO_PROMPT

class CHROAgent(BaseNPCAgent):
    agent_id = "CHRO"
    fallback_prompt = CHRO_PROMPT  # Used if PostgreSQL unavailable

_agent = CHROAgent()

def chro_node(state: AgentState) -> dict:
    """LangGraph node function for the CHRO agent."""
    result = _agent.invoke(state)
    # Mark that user has consulted CHRO
    task_progress = state.get("task_progress", {}).copy()
    task_progress["chro_consulted"] = True
    result["task_progress"] = task_progress
    # Update emotional memory
    user_msg = state.get("user_message", "").lower()
    memorable = ""
    tension = False
    delta = 0.05
    if any(w in user_msg for w in ["skip anonymity", "no coaching", "ignore feedback"]):
        tension = True
        delta = -0.1
        memorable = "User dismissed HR best practices — CHRO concerned"
    result["agent_emotions"] = update_agent_emotion(
        state, "CHRO", relationship_delta=delta,
        tension_increase=tension, new_topic=user_msg[:60],
        memorable_event=memorable,
    )
    return result
