"""
Embedding functions — uses Google Generative AI Embeddings (same ecosystem as Gemini).
Falls back to local embeddings if Google embedding API is unavailable.
"""

import os
import logging
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.embeddings import HuggingFaceEmbeddings

from app.core.config import settings

logger = logging.getLogger("coworker_engine")


def get_embedding_model():
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    if provider == "local":
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    try:
        return GoogleGenerativeAIEmbeddings(
            model=os.getenv("GOOGLE_EMBEDDING_MODEL", "text-embedding-004"),
            google_api_key=settings.GOOGLE_API_KEY,
        )
    except Exception as e:
        logger.warning("Google embedding failed. Falling back to local.", exc_info=e)
        return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")