"""Supervisor Node — routes each user message to the appropriate AI Co-worker."""

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.logging import logger
from app.engine.state import AgentState
from app.personas.prompts import SUPERVISOR_PROMPT

def _format_messages_for_supervisor(state: AgentState) -> str:
    """Format recent messages as a readable string for the supervisor prompt."""
    from langchain_core.messages import AIMessage
    recent = state["messages"][-10:]  # Last 10 messages for context
    lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            role = "User"
        elif isinstance(msg, AIMessage):
            role = msg.additional_kwargs.get("agent_id", "Agent")
        else:
            role = "System"
        content = msg.content[:200]  # Truncate for efficiency
        lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(No prior messages)"

def _format_task_progress(state: AgentState) -> str:
    """Format task progress as a readable checklist."""
    progress = state.get("task_progress", {})
    lines = []
    for task, done in progress.items():
        status = "[x]" if done else "[ ]"
        lines.append(f"  {status} {task}")
    return "\n".join(lines) if lines else "(No tasks tracked)"

def supervisor_node(state: AgentState) -> dict:
    """
    The Supervisor analyzes the user's message and returns a routing decision.

    Returns:
        dict with "next_speaker" set to one of:
        CEO | CHRO | RegionalManager | Mentor | SafetyBlock
    """
    # If user explicitly selected an agent via UI, honor that choice
    user_selected = state.get("next_speaker", "")
    valid_agents = {"CEO", "CHRO", "RegionalManager"}
    
    if user_selected in valid_agents:
        logger.info(f"User explicitly selected: {user_selected} — respecting choice")
        return {
            "next_speaker": user_selected,
            "turn_count": state.get("turn_count", 0) + 1,
        }
    
    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.0,  # Deterministic routing
        max_output_tokens=20,  # We only need one word
    )

    prompt = SUPERVISOR_PROMPT.format(
        messages=_format_messages_for_supervisor(state),
        task_progress=_format_task_progress(state),
        previous_speaker=state.get("previous_speaker", "none"),
        user_message=state["user_message"],
    )

    response = llm.invoke(prompt)
    raw_decision = response.content.strip().split()[0] if response.content.strip() else "CEO"
    # Remove any quotes/punctuation the LLM might add
    decision = raw_decision.strip('"\' .,;:')

    # The Supervisor should ONLY route to content-based agents or SafetyBlock.
    # Mentor is NEVER selected by the Supervisor — only the Director can trigger Mentor.
    valid_speakers = {"CEO", "CHRO", "RegionalManager", "SafetyBlock"}
    if decision == "Mentor":
        # LLM incorrectly chose Mentor — re-route based on content keywords
        decision = _fallback_keyword_route(state["user_message"])
        logger.warning(f"Supervisor tried to route to Mentor — overriding to {decision} via keyword fallback")
    elif decision not in valid_speakers:
        logger.warning(f"Supervisor returned invalid decision: '{decision}'. Defaulting to CEO.")
        decision = "CEO"

    logger.info(f"Supervisor auto-routed to: {decision}")

    return {
        "next_speaker": decision,
        "turn_count": state.get("turn_count", 0) + 1,
    }


def _fallback_keyword_route(user_message: str) -> str:
    """
    Keyword-based fallback routing when the LLM incorrectly routes to Mentor.
    Scans the user message for domain keywords and picks the best agent.
    """
    msg = user_message.lower()

    ceo_keywords = [
        "strategy", "brand", "dna", "mission", "culture", "autonomy", "vision",
        "budget", "craftsmanship", "heritage", "innovation", "technology",
        "luxury", "identity", "standardization", "centralization", "values",
        "ceo", "group dna", "brand autonomy",
    ]
    chro_keywords = [
        "hr", "competency", "competencies", "360", "feedback", "coaching",
        "talent", "pillar", "pillars", "behavioral", "performance", "training",
        "framework", "vision entrepreneurship passion trust", "chro",
    ]
    regional_keywords = [
        "regional", "europe", "rollout", "france", "italy", "uk", "germany",
        "timeline", "q3", "pilot", "cascade", "logistics", "local",
        "train-the-trainer", "regional manager",
    ]

    ceo_score = sum(1 for kw in ceo_keywords if kw in msg)
    chro_score = sum(1 for kw in chro_keywords if kw in msg)
    regional_score = sum(1 for kw in regional_keywords if kw in msg)

    if regional_score > ceo_score and regional_score > chro_score:
        return "RegionalManager"
    if chro_score > ceo_score:
        return "CHRO"
    return "CEO"  # Default to CEO for strategy/general questions
