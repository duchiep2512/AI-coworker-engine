"""
CEO Agent — Gucci Group CEO node.
Defends Group DNA, brand autonomy, and strategic vision.
"""

from app.engine.agents.base_agent import BaseNPCAgent
from app.engine.state import AgentState, update_agent_emotion
from app.personas.prompts import CEO_PROMPT

class CEOAgent(BaseNPCAgent):
    agent_id = "CEO"
    fallback_prompt = CEO_PROMPT  # Used if PostgreSQL unavailable

_agent = CEOAgent()

def ceo_node(state: AgentState) -> dict:
    """LangGraph node function for the CEO agent."""
    result = _agent.invoke(state)
    # Mark that user has consulted CEO
    task_progress = state.get("task_progress", {}).copy()
    task_progress["ceo_consulted"] = True
    result["task_progress"] = task_progress
    # Update emotional memory
    user_msg = state.get("user_message", "").lower()
    memorable = ""
    tension = False
    delta = 0.05  # Default slight positive
    if any(w in user_msg for w in ["standardiz", "centraliz", "uniform", "same for all"]):
        tension = True
        delta = -0.1
        memorable = "User proposed standardization — CEO pushed back"
    result["agent_emotions"] = update_agent_emotion(
        state, "CEO", relationship_delta=delta,
        tension_increase=tension, new_topic=user_msg[:60],
        memorable_event=memorable,
    )
    return result
