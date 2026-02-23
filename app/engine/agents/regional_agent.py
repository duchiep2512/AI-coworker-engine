"""
Regional Manager Agent — Employer Branding & Internal Comms (Europe) node.
Shares on-the-ground rollout insights, training needs, and regional challenges.
"""

from app.engine.agents.base_agent import BaseNPCAgent
from app.engine.state import AgentState, update_agent_emotion
from app.personas.prompts import REGIONAL_MANAGER_PROMPT

class RegionalManagerAgent(BaseNPCAgent):
    agent_id = "RegionalManager"
    fallback_prompt = REGIONAL_MANAGER_PROMPT  # Used if PostgreSQL unavailable

_agent = RegionalManagerAgent()

async def regional_manager_node(state: AgentState) -> dict:
    """LangGraph node function for the Regional Manager agent."""
    result = await _agent.ainvoke(state)
    # Mark that user has consulted Regional Manager
    task_progress = state.get("task_progress", {}).copy()
    task_progress["regional_manager_consulted"] = True
    result["task_progress"] = task_progress
    # Update emotional memory
    user_msg = state.get("user_message", "").lower()
    memorable = ""
    tension = False
    delta = 0.05
    if any(w in user_msg for w in ["q3 rollout", "september", "rush", "same everywhere"]):
        tension = True
        delta = -0.1
        memorable = "User pushed aggressive timeline — Regional Manager resisted"
    result["agent_emotions"] = update_agent_emotion(
        state, "RegionalManager", relationship_delta=delta,
        tension_increase=tension, new_topic=user_msg[:60],
        memorable_event=memorable,
    )
    return result
