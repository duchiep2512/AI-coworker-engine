"""
Context Retriever — fetches relevant knowledge for an agent before LLM generation.
"""

from typing import List

from langchain_core.documents import Document

from app.db.vector.faiss_store import retrieve
from app.core.logging import logger

def get_context_for_agent(query: str, agent_id: str, top_k: int = 3) -> str:
    """
    Retrieve relevant context from FAISS for a specific agent.

    Args:
        query: The user's message.
        agent_id: One of 'CEO', 'CHRO', 'RegionalManager'.
        top_k: Number of chunks to retrieve.

    Returns:
        Formatted context string to inject into the agent's prompt.
    """
    docs: List[Document] = retrieve(query, role_key=agent_id, top_k=top_k)

    if not docs:
        logger.warning(f"No relevant context found for agent={agent_id}")
        return "(No specific reference documents available for this query.)"

    context_parts = []
    for i, doc in enumerate(docs, 1):
        topic = doc.metadata.get("topic", "general")
        context_parts.append(
            f"[Reference {i} — Topic: {topic}]\n{doc.page_content}"
        )

    context_str = "\n\n".join(context_parts)

    logger.info(
        f"Retrieved {len(docs)} chunks for agent={agent_id} "
        f"(topics: {[d.metadata.get('topic') for d in docs]})"
    )

    return context_str
