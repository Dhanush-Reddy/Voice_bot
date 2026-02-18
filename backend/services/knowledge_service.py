"""
KnowledgeService — Sprint 5: Knowledge Base & RAG

Provides:
  - Document ingestion: text extraction, chunking, embedding via Gemini
  - In-memory vector store with cosine similarity search
  - Per-agent knowledge retrieval for RAG context injection

Architecture:
  - Embeddings: Google Gemini text-embedding-004 (768-dim)
  - Vector store: in-memory dict (Sprint 6 → Supabase pgvector)
  - Chunking: fixed-size with overlap (512 chars, 64 overlap)

Usage:
    doc = await knowledge_service.ingest(agent_id, filename, text_content)
    results = await knowledge_service.search(agent_id, query, top_k=3)
"""

import uuid
import logging
import math
import os
from typing import Optional, List
from datetime import datetime, timezone

from models.knowledge import KnowledgeDocument, KnowledgeChunk, KnowledgeSearchResult

logger = logging.getLogger(__name__)

# Chunking config
CHUNK_SIZE = 512       # characters per chunk
CHUNK_OVERLAP = 64     # overlap between consecutive chunks
MAX_CHUNKS_PER_DOC = 200

# In-memory stores
_documents: dict[str, KnowledgeDocument] = {}
_chunks: dict[str, KnowledgeChunk] = {}   # chunk_id → KnowledgeChunk


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _chunk_text(text: str) -> List[str]:
    """Split text into overlapping fixed-size chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks[:MAX_CHUNKS_PER_DOC]


async def _embed(text: str) -> Optional[List[float]]:
    """
    Generate an embedding for the given text using Gemini.

    Falls back to None if the API is unavailable (e.g., missing credentials).
    The vector store still works without embeddings — it falls back to
    keyword matching in that case.
    """
    try:
        import google.generativeai as genai

        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        # else: relies on ADC / GOOGLE_APPLICATION_CREDENTIALS

        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )
        return result["embedding"]
    except Exception as exc:
        logger.warning("⚠️  Embedding failed (will use keyword fallback): %s", exc)
        return None


def _keyword_score(query: str, text: str) -> float:
    """Simple keyword overlap score as fallback when embeddings are unavailable."""
    query_words = set(query.lower().split())
    text_words = set(text.lower().split())
    if not query_words:
        return 0.0
    return len(query_words & text_words) / len(query_words)


class KnowledgeService:
    """Manages document ingestion and semantic search for agent knowledge bases."""

    async def ingest(
        self,
        agent_id: str,
        filename: str,
        text_content: str,
        content_type: str = "text/plain",
    ) -> KnowledgeDocument:
        """
        Ingest a document into the knowledge base.

        Steps:
          1. Chunk the text
          2. Embed each chunk via Gemini
          3. Store chunks in the in-memory vector store
          4. Return a KnowledgeDocument record
        """
        doc_id = str(uuid.uuid4())
        chunks = _chunk_text(text_content)
        logger.info(
            "📚 Ingesting document: agent=%s file=%s chunks=%d",
            agent_id, filename, len(chunks),
        )

        stored = 0
        for i, chunk_text in enumerate(chunks):
            embedding = await _embed(chunk_text)
            chunk = KnowledgeChunk(
                id=str(uuid.uuid4()),
                document_id=doc_id,
                agent_id=agent_id,
                text=chunk_text,
                embedding=embedding,
                metadata={"chunk_index": i, "filename": filename},
            )
            _chunks[chunk.id] = chunk
            stored += 1

        doc = KnowledgeDocument(
            id=doc_id,
            agent_id=agent_id,
            filename=filename,
            content_type=content_type,
            chunk_count=stored,
            size_bytes=len(text_content.encode()),
            created_at=datetime.now(timezone.utc),
        )
        _documents[doc_id] = doc
        logger.info("✅ Document ingested: id=%s chunks=%d", doc_id, stored)
        return doc

    async def search(
        self,
        agent_id: str,
        query: str,
        top_k: int = 3,
    ) -> List[KnowledgeSearchResult]:
        """
        Semantic search over the agent's knowledge base.

        Returns the top_k most relevant chunks.
        Falls back to keyword matching if embeddings are unavailable.
        """
        # Filter chunks for this agent
        agent_chunks = [c for c in _chunks.values() if c.agent_id == agent_id]
        if not agent_chunks:
            return []

        # Embed the query
        query_embedding = await _embed(query)

        results: List[tuple[float, KnowledgeChunk]] = []
        for chunk in agent_chunks:
            if query_embedding and chunk.embedding:
                score = _cosine_similarity(query_embedding, chunk.embedding)
            else:
                # Fallback: keyword overlap
                score = _keyword_score(query, chunk.text)
            results.append((score, chunk))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [
            KnowledgeSearchResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                text=chunk.text,
                score=round(score, 4),
                filename=chunk.metadata.get("filename") if chunk.metadata else None,
            )
            for score, chunk in results[:top_k]
        ]

    async def list_documents(self, agent_id: str) -> List[KnowledgeDocument]:
        """List all documents for a given agent."""
        return [d for d in _documents.values() if d.agent_id == agent_id]

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and all its chunks."""
        if document_id not in _documents:
            return False
        # Remove all chunks belonging to this document
        to_delete = [cid for cid, c in _chunks.items() if c.document_id == document_id]
        for cid in to_delete:
            del _chunks[cid]
        del _documents[document_id]
        logger.info("🗑️  Document deleted: id=%s (%d chunks removed)", document_id, len(to_delete))
        return True

    def stats(self, agent_id: Optional[str] = None) -> dict:
        """Return knowledge base statistics."""
        docs = list(_documents.values())
        chunks = list(_chunks.values())
        if agent_id:
            docs = [d for d in docs if d.agent_id == agent_id]
            chunks = [c for c in chunks if c.agent_id == agent_id]
        return {
            "documents": len(docs),
            "chunks": len(chunks),
            "has_embeddings": any(c.embedding for c in chunks),
        }


# Module-level singleton
knowledge_service = KnowledgeService()
