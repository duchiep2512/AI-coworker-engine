"""
Knowledge Base Ingestion — reads source documents, chunks them,
tags with metadata, and builds role-specific FAISS indices.
"""

import re
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.core.logging import logger
from app.db.vector.faiss_store import build_index

# Metadata rules: which sections belong to which role
SECTION_ROLE_MAP = {
    1: {"roles": ["CEO", "shared"], "topic": "group_dna"},
    2: {"roles": ["CHRO", "shared"], "topic": "competency_framework"},
    3: {"roles": ["CHRO"], "topic": "360_coaching"},
    4: {"roles": ["RegionalManager"], "topic": "regional_rollout"},
    5: {"roles": ["shared"], "topic": "simulation_tasks"},
}

def _parse_sections(raw_text: str) -> List[dict]:
    """
    Parse the document into sections by finding 'SECTION N:' headers.
    Returns list of {"section_num": int, "text": str, "meta": dict}.
    """
    # Find all section boundaries
    pattern = r'SECTION\s+(\d+)\s*:'
    matches = list(re.finditer(pattern, raw_text))

    sections = []
    for i, match in enumerate(matches):
        section_num = int(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw_text)

        section_text = raw_text[start:end].strip()
        meta = SECTION_ROLE_MAP.get(section_num, {"roles": ["shared"], "topic": "general"})

        sections.append({
            "section_num": section_num,
            "text": section_text,
            "meta": meta,
        })
        logger.info(f"  Parsed SECTION {section_num}: {len(section_text)} chars → roles={meta['roles']}")

    return sections

def load_and_chunk(file_path: Path, chunk_size: int = 500, chunk_overlap: int = 80) -> List[Document]:
    """
    Load a text file, split into chunks, and attach role-based metadata.
    """
    logger.info(f"Reading source file: {file_path}")
    raw_text = file_path.read_text(encoding="utf-8")

    # Parse into sections (keeps header+content together)
    sections = _parse_sections(raw_text)

    if not sections:
        logger.error("No sections found in document! Check format.")
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " "],
    )

    all_docs: List[Document] = []

    for section in sections:
        chunks = splitter.split_text(section["text"])

        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": file_path.name,
                    "section": section["section_num"],
                    "role_access": section["meta"]["roles"],
                    "topic": section["meta"]["topic"],
                    "chunk_index": i,
                },
            )
            all_docs.append(doc)

        logger.info(
            f"  Section {section['section_num']}: {len(chunks)} chunks "
            f"→ {section['meta']['roles']}"
        )

    logger.info(f"  Total: {len(all_docs)} chunks from {file_path.name}")
    return all_docs

def build_role_indices(documents: List[Document]) -> None:
    """
    Distribute documents into role-specific FAISS indices.

    A document tagged with role_access=["CEO", "shared"] will be added
    to BOTH the CEO index and the shared index.
    """
    role_buckets: dict[str, List[Document]] = {
        "CEO": [],
        "CHRO": [],
        "RegionalManager": [],
        "shared": [],
    }

    for doc in documents:
        for role in doc.metadata.get("role_access", ["shared"]):
            if role in role_buckets:
                role_buckets[role].append(doc)

    for role, docs in role_buckets.items():
        if docs:
            build_index(docs, role)
            logger.info(f"  └── {role}: {len(docs)} chunks indexed")
        else:
            logger.warning(f"  └── {role}: No documents found — skipping index")

def ingest():
    """Main ingestion pipeline — call this to (re)build all FAISS indices."""
    source_file = settings.knowledge_dir / "gucci_2.0.txt"

    if not source_file.exists():
        logger.error(f" Source file not found: {source_file}")
        return

    documents = load_and_chunk(source_file)
    build_role_indices(documents)
    logger.info(" Knowledge base ingestion complete!")

if __name__ == "__main__":
    ingest()
