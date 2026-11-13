"""Build the tax assistant's corpus: `python -m app.rag.build` (feature 006, task T007; R1).

Reads `sources.yaml`, takes each FBR file from the cache (or downloads it), and stops if its
SHA-256 differs from the pinned one (FR-002: a file FBR changed silently never reaches the
corpus). Then it reads the named pages, splits them into passages and embeds them. Only when
every step has worked does it replace the stored corpus, in one transaction; any failure leaves
the previous corpus as it was, so the assistant keeps working (design addendum, builder check).
Run it locally, and once on the VM after a deploy that changes the sources.
"""

import asyncio
import hashlib
import logging
import os
import sys
from collections.abc import Awaitable, Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx2
import yaml
from pypdf import PdfReader
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.rag.embed import EMBEDDING_MODEL, Embedder, EmbeddingError, GeminiEmbedder
from app.rag.models import CorpusDocument, DocumentKind, Passage
from app.rag.split import Part, RawPassage, split_guidance, split_law
from app.telemetry.ai import ai_call

logger = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).with_name("sources.yaml")
# Inside the backend folder (mounted in Docker), so downloads survive container restarts;
# git- and docker-ignored, so FBR's files are never committed (FR-002).
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus-cache"

Download = Callable[[str], Awaitable[bytes]]
ReadPages = Callable[[Path, set[int]], dict[int, str]]


class BuildError(Exception):
    """The corpus couldn't be built; the previous one is unchanged."""


@dataclass(frozen=True)
class Source:
    """One FBR file, as sources.yaml names it."""

    id: str
    title: str
    kind: DocumentKind
    url: str
    sha256: str
    parts: tuple[Part, ...]


def load_sources(path: Path = SOURCES_FILE) -> list[Source]:
    """The FBR sources the assistant may use, from sources.yaml."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    sources = []
    for doc in data["documents"]:
        kind = DocumentKind(doc["kind"])
        key, items = (
            ("section", doc["sections"])
            if kind is DocumentKind.LAW
            else ("chapter", doc["chapters"])
        )
        parts = tuple(Part(str(item[key]), (item["pages"][0], item["pages"][1])) for item in items)
        sources.append(Source(doc["id"], doc["title"], kind, doc["url"], doc["sha256"], parts))
    return sources


async def build_corpus(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    db: AsyncSession,
    sources: Sequence[Source],
    cache_dir: Path,
    download: Download,
    read_pages: ReadPages,
    embedder: Embedder,
) -> int:
    """Replace the corpus with these sources; returns the number of passages. Nothing is
    written unless everything (files, checksums, splitting, embedding) has worked; the caller
    commits."""
    prepared = [await _passages_of(source, cache_dir, download, read_pages) for source in sources]
    texts = [p.text for _, passages in prepared for p in passages]
    try:
        with ai_call("embeddings", EMBEDDING_MODEL, "embeddings"):
            vectors = await embedder.embed_documents(texts)
    except EmbeddingError as exc:
        raise BuildError(f"Embedding failed: {exc}") from exc
    await _replace_corpus(db, prepared, iter(vectors))
    return len(texts)


async def _passages_of(
    source: Source, cache_dir: Path, download: Download, read_pages: ReadPages
) -> tuple[Source, list[RawPassage]]:
    """The verified file's named pages, split into passages."""
    path = await _verified_file(source, cache_dir, download)
    needed = {n for part in source.parts for n in range(part.pages[0], part.pages[1] + 1)}
    split = split_law if source.kind is DocumentKind.LAW else split_guidance
    passages = split(read_pages(path, needed), list(source.parts))
    if not passages:
        raise BuildError(f"{source.id}: no passages found; check its pages in sources.yaml.")
    return source, passages


async def _replace_corpus(
    db: AsyncSession,
    prepared: list[tuple[Source, list[RawPassage]]],
    vectors: Iterator[list[float]],
) -> None:
    """Delete the old corpus (passages go with their documents) and store the new one."""
    await db.execute(delete(CorpusDocument))
    now = datetime.now(UTC)
    for source, passages in prepared:
        db.add(
            CorpusDocument(
                id=source.id,
                title=source.title,
                kind=source.kind,
                url=source.url,
                sha256=source.sha256,
                built_at=now,
            )
        )
        await db.flush()
        db.add_all(
            Passage(
                document_id=source.id,
                location=p.location,
                page=p.page,
                text=p.text,
                embedding=next(vectors),
            )
            for p in passages
        )
    await db.flush()


async def _verified_file(source: Source, cache_dir: Path, download: Download) -> Path:
    """The source's file from the cache, downloaded (again) if missing or not the pinned one."""
    path = cache_dir / f"{source.id}.pdf"
    if path.exists() and _sha256(path.read_bytes()) == source.sha256:
        return path
    content = await download(source.url)
    if _sha256(content) != source.sha256:
        raise BuildError(
            f"{source.id}: the file at {source.url} is not the pinned version (its SHA-256 "
            "differs). FBR may have changed it; check it and update sources.yaml."
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


async def download_from_fbr(url: str) -> bytes:
    """Fetch one file from FBR's site (redirects followed; a generous timeout for big PDFs)."""
    async with httpx2.AsyncClient(follow_redirects=True, timeout=180) as http:
        response = await http.get(url)
        response.raise_for_status()
        return response.content


def read_pdf_pages(path: Path, numbers: set[int]) -> dict[int, str]:
    """The text of the given 1-based pages of a PDF."""
    reader = PdfReader(path)
    return {n: reader.pages[n - 1].extract_text() or "" for n in sorted(numbers)}


async def _main() -> int:
    embedder = GeminiEmbedder(api_key=os.environ.get("GEMINI_API_KEY", "").strip() or None)
    async with get_sessionmaker()() as db:
        try:
            count = await build_corpus(
                db, load_sources(), CACHE_DIR, download_from_fbr, read_pdf_pages, embedder
            )
        except (BuildError, httpx2.HTTPError) as exc:
            print(f"Corpus not built; the previous one is unchanged. {exc}", file=sys.stderr)
            return 1
        await db.commit()
    print(f"Corpus built: {count} passages.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(asyncio.run(_main()))
