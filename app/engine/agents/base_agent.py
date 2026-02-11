"""Base NPC Agent — abstract class that all AI Co-workers inherit from."""

import asyncio
from abc import ABC
from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.logging import logger
from app.engine.state import AgentState, get_emotional_context
from app.knowledge.retriever import get_context_for_agent

class BaseNPCAgent(ABC):
    """
    Abstract base class for all NPC (AI Co-worker) agents.

    Subclasses must define:
      - agent_id: str (e.g., "CEO")
      - fallback_prompt: str (hardcoded prompt if DB not available)
    """

    agent_id: str = ""
    fallback_prompt: str = ""

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=settings.GEMINI_TEMPERATURE,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
        )

    async def _get_system_prompt(self) -> str:
        """
        Get system prompt from PostgreSQL (via agent_loader cache).
        Falls back to hardcoded prompt if DB unavailable.
        """
        try:
            from app.db.agent_loader import get_system_prompt
            prompt = await get_system_prompt(self.agent_id)
            if prompt:
                return prompt
        except Exception as e:
            logger.debug(f"Could not load {self.agent_id} prompt from DB: {e}")
        
        return self.fallback_prompt

    def _format_chat_history(self, messages: List[BaseMessage], max_turns: int = 8) -> str:
        """Format recent chat history with agent names for cross-agent memory."""
        recent = messages[-max_turns * 2:]  # last N exchanges
        lines = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                lines.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                # Tag with agent name so other agents know who said what
                agent_name = msg.additional_kwargs.get("agent_id", "Agent")
                lines.append(f"{agent_name}: {msg.content}")
        return "\n".join(lines) if lines else "(This is the start of the conversation.)"

    async def _build_prompt(self, state: AgentState) -> str:
        """Build the full prompt by injecting context, history, and user message."""
        # Retrieve relevant knowledge from FAISS
        context = get_context_for_agent(
            query=state["user_message"],
            agent_id=self.agent_id,
            top_k=3,
        )

        # Format chat history
        chat_history = self._format_chat_history(state["messages"])

        # Get emotional context for this agent
        emotional_ctx = get_emotional_context(state, self.agent_id)
        if emotional_ctx:
            context = emotional_ctx + "\n\n" + context

        # Get system prompt (from DB or fallback)
        system_prompt = await self._get_system_prompt()

        # Build prompt from template
        prompt = system_prompt.format(
            context=context,
            chat_history=chat_history,
            user_message=state["user_message"],
            task_progress=str(state.get("task_progress", {})),
        )

        return prompt

    async def ainvoke(self, state: AgentState) -> dict:
        """
        Async generate a response from this NPC agent.

        Args:
            state: Current AgentState.

        Returns:
            dict with updated messages and previous_speaker.
        """
        prompt = await self._build_prompt(state)

        logger.info(f"{self.agent_id} generating response...")
        response = await self.llm.ainvoke(prompt)

        # Tag the response with agent identity
        agent_message = AIMessage(
            content=response.content,
            additional_kwargs={"agent_id": self.agent_id},
        )

        logger.info(f"{self.agent_id} responded ({len(response.content)} chars)")

        return {
            "messages": [agent_message],
            "previous_speaker": self.agent_id,
        }

    def invoke(self, state: AgentState) -> dict:
        """
        Sync wrapper for backward compatibility.
        Runs the async ainvoke in an event loop.
        """
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, use create_task
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))
        except RuntimeError:
            # No event loop running, safe to use run_until_complete
            return asyncio.get_event_loop().run_until_complete(self.ainvoke(state))
