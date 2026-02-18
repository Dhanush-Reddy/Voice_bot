"""
Pydantic models for Knowledge Base documents.

Sprint 5: RAG (Retrieval-Augmented Generation)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeDocument(BaseModel):
    """A document stored in the knowledge base for a given agent."""

    id: str
    agent_id: str
    filename: str
    content_type: str = Field(default="text/plain", description="MIME type of the uploaded file")
    chunk_count: int = Field(default=0, description="Number of text chunks indexed")
    size_bytes: int = Field(default=0)
    created_at: Optional[datetime] = None


class KnowledgeChunk(BaseModel):
    """A single searchable chunk of a document with its embedding."""

    id: str
    document_id: str
    agent_id: str
    text: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeSearchResult(BaseModel):
    """A search result from the vector store."""

    chunk_id: str
    document_id: str
    text: str
    score: float = Field(description="Cosine similarity score (0–1)")
    filename: Optional[str] = None
