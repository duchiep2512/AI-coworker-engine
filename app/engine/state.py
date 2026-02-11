"""Agent State — the shared memory object passed between all LangGraph nodes."""

from typing import Annotated, Any, Dict, List, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

class EmotionalMemory(TypedDict):
    """
    Tracks the emotional state of each agent towards the user.
    This enables "Turn 1 affects Turn 5" behavior.
    """
    # How much this agent trusts/likes the user (0.0 = hostile, 1.0 = trusting)
    relationship_score: float
    # Count of times user has irritated this agent
    tension_count: int
    # Last interaction topic (for continuity)
    last_topic: str
    # Notable events to remember
    memorable_events: List[str]

class AgentState(TypedDict):
    """
    Shared state flowing through the LangGraph state machine.

    Fields:
    -------
    messages : list[BaseMessage]
        Full conversation history (auto-appended via `add_messages` reducer).

    next_speaker : str
        The agent selected by the Supervisor to respond next.
        One of: "CEO", "CHRO", "RegionalManager", "Mentor", "SafetyBlock", "__end__"

    previous_speaker : str
        Who spoke last (enables Sticky Routing — continuing conversations).

    user_message : str
        The raw latest message from the user (convenience field for prompts).

    sentiment_score : float
        Estimated user sentiment: 0.0 = frustrated → 1.0 = confident.

    turn_count : int
        Number of interaction turns in this session.

    stuck_counter : int
        How many turns the user has been "unproductive". Reset when progress is made.

    task_progress : dict
        Tracks which simulation objectives have been completed.
        Example: {"ceo_consulted": True, "competency_model_drafted": False}

    hint_triggered : bool
        Whether the Director triggered a Mentor hint on this turn.

    safety_flagged : bool
        Whether this turn was blocked by safety guardrails.

    agent_emotions : dict
        Per-agent emotional state tracking. Key = agent_id (CEO, CHRO, etc.)
        Value = EmotionalMemory dict.
        
    user_approach_style : str
        Detected communication style: "collaborative", "aggressive", "passive", "analytical"
        
    repeated_mistakes : list
        Track patterns of user behavior that agents should remember.
        E.g., ["ignored_ceo_concern", "skipped_chro_input"]
        
    session_narrative : str
        Running summary of key conversation events for long-term context.
    """

    messages: Annotated[List[BaseMessage], add_messages]
    next_speaker: str
    previous_speaker: str
    user_message: str

    sentiment_score: float
    turn_count: int
    stuck_counter: int

    task_progress: Dict[str, Any]

    hint_triggered: bool
    safety_flagged: bool
    user_explicit_choice: bool

    agent_emotions: Dict[str, EmotionalMemory]
    user_approach_style: str
    repeated_mistakes: List[str]
    session_narrative: str

DEFAULT_TASK_PROGRESS = {
    "problem_statement_written": False,
    "ceo_consulted": False,
    "chro_consulted": False,
    "competency_model_drafted": False,
    "360_program_designed": False,
    "regional_manager_consulted": False,
    "rollout_plan_built": False,
    "kpi_table_defined": False,
}

def create_default_emotional_memory() -> EmotionalMemory:
    """Create neutral emotional state for an agent."""
    return EmotionalMemory(
        relationship_score=0.5,  # Start neutral
        tension_count=0,
        last_topic="",
        memorable_events=[],
    )

def create_initial_state(user_message: str) -> AgentState:
    """Create a fresh state for a new simulation session."""
    return AgentState(
        messages=[],
        next_speaker="",
        previous_speaker="",
        user_message=user_message,
        sentiment_score=0.5,
        turn_count=0,
        stuck_counter=0,
        task_progress=DEFAULT_TASK_PROGRESS.copy(),
        hint_triggered=False,
        safety_flagged=False,
        user_explicit_choice=False,  # Default to auto-route mode
        # New emotional memory fields
        agent_emotions={
            "CEO": create_default_emotional_memory(),
            "CHRO": create_default_emotional_memory(),
            "RegionalManager": create_default_emotional_memory(),
        },
        user_approach_style="unknown",
        repeated_mistakes=[],
        session_narrative="",
    )

#  EMOTIONAL MEMORY HELPERS

def update_agent_emotion(
    state: AgentState,
    agent_id: str,
    relationship_delta: float = 0.0,
    tension_increase: bool = False,
    new_topic: str = "",
    memorable_event: str = "",
) -> Dict[str, EmotionalMemory]:
    """
    Update an agent's emotional state towards the user.
    
    Args:
        state: Current agent state
        agent_id: Which agent to update (CEO, CHRO, RegionalManager)
        relationship_delta: How much to change relationship_score (+/-)
        tension_increase: Whether to increment tension_count
        new_topic: Update last_topic if provided
        memorable_event: Add to memorable_events if provided
    
    Returns:
        Updated agent_emotions dict
    """
    emotions = state.get("agent_emotions", {}).copy()
    
    if agent_id not in emotions:
        emotions[agent_id] = create_default_emotional_memory()
    
    agent_emo = dict(emotions[agent_id])  # Make copy
    
    # Update relationship score (bounded 0.0 - 1.0)
    new_score = agent_emo["relationship_score"] + relationship_delta
    agent_emo["relationship_score"] = max(0.0, min(1.0, new_score))
    
    # Update tension
    if tension_increase:
        agent_emo["tension_count"] += 1
    
    # Update topic
    if new_topic:
        agent_emo["last_topic"] = new_topic
    
    # Add memorable event (keep last 5)
    if memorable_event:
        events = list(agent_emo["memorable_events"])
        events.append(memorable_event)
        agent_emo["memorable_events"] = events[-5:]
    
    emotions[agent_id] = agent_emo
    return emotions

def get_emotional_context(state: AgentState, agent_id: str) -> str:
    """
    Generate emotional context string for prompt injection.
    
    This tells the agent how to adjust their tone based on past interactions.
    """
    emotions = state.get("agent_emotions", {})
    if agent_id not in emotions:
        return ""
    
    emo = emotions[agent_id]
    score = emo.get("relationship_score", 0.5)
    tension = emo.get("tension_count", 0)
    events = emo.get("memorable_events", [])
    
    context_parts = []
    
    # Relationship-based tone adjustment
    if score < 0.3:
        context_parts.append(
            "EMOTIONAL STATE: You are frustrated with this user. "
            "Be more reserved, direct, and less forthcoming. "
            "They need to rebuild trust with you."
        )
    elif score < 0.5:
        context_parts.append(
            "EMOTIONAL STATE: You are somewhat wary of this user. "
            "Be professional but guarded. Wait for them to show good faith."
        )
    elif score > 0.7:
        context_parts.append(
            "EMOTIONAL STATE: You like this user. Be warm, helpful, and "
            "share more detailed insights. They've earned your trust."
        )
    
    # Tension-based escalation
    if tension >= 3:
        context_parts.append(
            f"HIGH TENSION: User has pushed your boundaries {tension} times. "
            "You may be more blunt or redirect to another colleague."
        )
    elif tension >= 1:
        context_parts.append(
            f"SOME TENSION: User has tested your patience before. Stay alert."
        )
    
    # Memorable events
    if events:
        events_str = "; ".join(events[-3:])
        context_parts.append(f"REMEMBER: {events_str}")
    
    return "\n".join(context_parts)
