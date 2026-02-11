"""
FAISS Vector Store — role-specific knowledge indices.
"""

from pathlib import Path
from typing import List, Optional

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.core.config import settings
from app.core.logging import logger
from app.db.vector.embeddings import get_embedding_model

ROLE_INDEX_MAP = {
    "CEO": "ceo",
    "CHRO": "chro",
    "RegionalManager": "regional",
    "shared": "shared",
}

def _index_path(role_key: str) -> Path:
    """Resolve the FAISS index directory for a given role."""
    return settings.faiss_index_path / ROLE_INDEX_MAP.get(role_key, "shared")

#  BUILD / SAVE

def build_index(documents: List[Document], role_key: str) -> FAISS:
    """
    Build a FAISS index from a list of LangChain Documents and persist to disk.

    Args:
        documents: Pre-chunked documents with metadata.
        role_key: One of 'CEO', 'CHRO', 'RegionalManager', 'shared'.
    """
    embeddings = get_embedding_model()
    vectorstore = FAISS.from_documents(documents, embeddings)

    save_path = _index_path(role_key)
    save_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(save_path))
    logger.info(f"FAISS index saved → {save_path}  ({len(documents)} chunks)")
    return vectorstore

#  LOAD / QUERY

def load_index(role_key: str) -> Optional[FAISS]:
    """Load a persisted FAISS index for the given role."""
    index_path = _index_path(role_key)
    if not index_path.exists():
        logger.warning(f"FAISS index not found at {index_path}")
        return None

    embeddings = get_embedding_model()
    vectorstore = FAISS.load_local(
        str(index_path),
        embeddings,
        allow_dangerous_deserialization=True,
    )
    logger.info(f"FAISS index loaded ← {index_path}")
    return vectorstore

def retrieve(query: str, role_key: str, top_k: int = 3) -> List[Document]:
    """
    Retrieve the most relevant chunks for a query from the role-specific index.
    Falls back to shared index if role-specific index is empty.

    Args:
        query: User's question or message.
        role_key: Which agent is asking ('CEO', 'CHRO', 'RegionalManager').
        top_k: Number of chunks to return.

    Returns:
        List of relevant LangChain Documents.
    """
    results: List[Document] = []

    # 1. Try role-specific index
    role_store = load_index(role_key)
    if role_store:
        results = role_store.similarity_search(query, k=top_k)

    # 2. Supplement with shared index ONLY if role-specific didn't fill top_k
    remaining = top_k - len(results)
    if remaining > 0:
        shared_store = load_index("shared")
        if shared_store:
            shared_results = shared_store.similarity_search(query, k=remaining)
            results.extend(shared_results)

    return results[:top_k]
