"""Finding the passages that answer a question (feature 006, task T008; research R4).

The question is embedded as a query and compared with every passage by cosine similarity over
the HNSW index; the top 5 come back with what a citation needs. A question is "not covered"
when even the best passage is below the relevance cut-off, a plain-code rule the eval can
measure without asking the AI (FR-006). Used by the Ask page and the MCP search tool alike.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embed import EMBEDDING_MODEL, Embedder
from app.rag.models import CorpusDocument, DocumentKind, Passage
from app.rag.settings import RELEVANCE_CUTOFF, TOP_K
from app.telemetry.ai import ai_call


@dataclass(frozen=True)
class RetrievedPassage:  # pylint: disable=too-many-instance-attributes  # one field per citation part
    """A passage found for a question, with its citation and how close it is (1 = same)."""

    id: uuid.UUID
    title: str
    kind: DocumentKind
    location: str
    page: int
    text: str
    score: float


@dataclass(frozen=True)
class SearchResult:
    """The nearest passages, best first, and whether the best is relevant enough to use."""

    passages: list[RetrievedPassage]
    covered: bool


async def search(
    db: AsyncSession,
    embedder: Embedder,
    question: str,
    *,
    top_k: int = TOP_K,
    cutoff: float = RELEVANCE_CUTOFF,
) -> SearchResult:
    """The top passages for a question, nearest first."""
    with ai_call("embeddings", EMBEDDING_MODEL, "embeddings"):
        vector = await embedder.embed_query(question)
    distance = Passage.embedding.cosine_distance(vector)
    rows = (
        await db.execute(
            select(Passage, CorpusDocument.title, CorpusDocument.kind, distance)
            .join(CorpusDocument, CorpusDocument.id == Passage.document_id)
            .order_by(distance)
            .limit(top_k)
        )
    ).all()
    passages = [
        RetrievedPassage(
            id=passage.id,
            title=title,
            kind=kind,
            location=passage.location,
            page=passage.page,
            text=passage.text,
            score=1.0 - float(dist),
        )
        for passage, title, kind, dist in rows
    ]
    covered = bool(passages) and passages[0].score >= cutoff
    return SearchResult(passages, covered)
