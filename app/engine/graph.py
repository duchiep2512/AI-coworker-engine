"""
LangGraph State Machine — Multi-Agent Supervisor with Director Override.

Flow: User Message -> Supervisor -> Director -> Agent -> Response.
"""

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from app.core.logging import logger
from app.engine.state import AgentState, create_initial_state
from app.engine.supervisor import supervisor_node
from app.engine.director import director_check
from app.engine.agents.ceo_agent import ceo_node
from app.engine.agents.chro_agent import chro_node
from app.engine.agents.regional_agent import regional_manager_node
from app.engine.agents.mentor_agent import mentor_node
from app.personas.prompts import SAFETY_BLOCK_RESPONSE

def safety_block_node(state: AgentState) -> dict:
    """Return a safety response when jailbreak / off-topic is detected."""
    logger.warning(f"Safety block triggered for message: {state['user_message'][:80]}...")

    block_message = AIMessage(
        content=SAFETY_BLOCK_RESPONSE,
        additional_kwargs={"agent_id": "System"},
    )

    return {
        "messages": [block_message],
        "previous_speaker": "System",
        "safety_flagged": True,
    }

def director_node(state: AgentState) -> dict:
    """
    The Director checks user progress and may override routing to Mentor.
    Runs AFTER Supervisor, BEFORE the selected agent.
    """
    return director_check(state)

def route_after_supervisor(state: AgentState) -> str:
    """Route to Director check after Supervisor makes initial decision."""
    return "Director"

def route_after_director(state: AgentState) -> str:
    """
    After Director runs, route to the actual agent.
    Director may have overridden next_speaker to "Mentor".
    """
    speaker = state.get("next_speaker", "CEO")

    route_map = {
        "CEO": "CEO",
        "CHRO": "CHRO",
        "RegionalManager": "RegionalManager",
        "Mentor": "Mentor",
        "SafetyBlock": "SafetyBlock",
    }

    destination = route_map.get(speaker, "CEO")
    logger.info(f"Routing to: {destination}")
    return destination

def build_graph() -> StateGraph:
    """
    Construct the LangGraph state machine.

    Flow:
        Supervisor → Director → [CEO | CHRO | RegionalManager | Mentor | SafetyBlock] → END
    """
    graph = StateGraph(AgentState)

    graph.add_node("Supervisor", supervisor_node)
    graph.add_node("Director", director_node)
    graph.add_node("CEO", ceo_node)
    graph.add_node("CHRO", chro_node)
    graph.add_node("RegionalManager", regional_manager_node)
    graph.add_node("Mentor", mentor_node)
    graph.add_node("SafetyBlock", safety_block_node)

    graph.set_entry_point("Supervisor")

    # Supervisor → always goes to Director first
    graph.add_edge("Supervisor", "Director")

    # Director → routes to the appropriate agent
    graph.add_conditional_edges(
        "Director",
        route_after_director,
        {
            "CEO": "CEO",
            "CHRO": "CHRO",
            "RegionalManager": "RegionalManager",
            "Mentor": "Mentor",
            "SafetyBlock": "SafetyBlock",
        },
    )

    # All agents → END (one turn per invocation)
    graph.add_edge("CEO", END)
    graph.add_edge("CHRO", END)
    graph.add_edge("RegionalManager", END)
    graph.add_edge("Mentor", END)
    graph.add_edge("SafetyBlock", END)

    return graph

def get_engine():
    """Compile and return the LangGraph engine."""
    graph = build_graph()
    engine = graph.compile()
    logger.info("AI Co-Worker Engine compiled and ready")
    return engine

# Pre-compiled engine instance
engine = get_engine()
