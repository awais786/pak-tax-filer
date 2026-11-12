"""Document logic as plain functions (feature 003, tasks T013, T018, T022; research R9).

Routers only translate HTTP; everything here can be tested without it. Other features read
figures only through confirmed_documents() (Principle III).
"""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.documents.extraction.client import Extractor
from app.documents.extraction.normalise import parse_amount, parse_tax_year
from app.documents.extraction.rules import check_rules, is_tax_year
from app.documents.extraction.schemas import ExtractedValue
from app.documents.models import (
    FIELDS_BY_TYPE,
    Confidence,
    DocStatus,
    DocType,
    Document,
    ExtractedField,
    ExtractionAttempt,
    FieldName,
)
from app.documents.storage import Storage
from app.documents.uploads import CheckedFile
from app.settings import get_settings
from app.telemetry.ai import ai_call, record_refusal, record_usage

# Reasons starting with this come from reading the printed value, not from a rule.
UNREADABLE = "Couldn't read"


class DocumentLocked(Exception):
    """The document isn't in a state that allows this change (HTTP 409)."""


class WrongDocumentType(Exception):
    """The document isn't the type the user chose (FR-005a); the message says what it looks like."""


class FieldNotOnDocument(LookupError):
    """The document's type has no field with that name (HTTP 404)."""


# FR-017 (added 2026-11-09): with open sign-up, no one user, and no number of new accounts,
# may use up the free AI quota.
DAILY_EXTRACTIONS = 10
APP_DAILY_EXTRACTIONS = 100
DAILY_WINDOW = timedelta(hours=24)
USER_LIMIT_REACHED = (
    f"Daily limit reached: {DAILY_EXTRACTIONS} extractions per 24 hours. Try again later."
)
APP_LIMIT_REACHED = "The app's daily extraction limit has been reached. Try again later."


class DailyLimitReached(Exception):
    """The user's or the whole app's extractions for the last 24 hours are used (HTTP 429)."""


async def use_extraction(db: AsyncSession, user_id: uuid.UUID) -> ExtractionAttempt:
    """Count one AI call for the user, or raise DailyLimitReached if a daily limit is used.

    One app-wide lock (held until the transaction ends) stops requests sent together from all
    reading the counts before any records an attempt, as with login throttling (002 R4). Callers
    commit soon after, before calling the AI, so the lock is held only for these two counts.
    """
    await db.execute(
        sql_text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": "extraction-attempts"},
    )
    since = datetime.now(UTC) - DAILY_WINDOW
    recent = select(func.count()).select_from(ExtractionAttempt)
    recent = recent.where(ExtractionAttempt.attempted_at > since)
    if (await db.execute(recent)).scalar_one() >= APP_DAILY_EXTRACTIONS:
        record_refusal("extraction", get_settings().extraction_model)
        raise DailyLimitReached(APP_LIMIT_REACHED)
    mine = recent.where(ExtractionAttempt.user_id == user_id)
    if (await db.execute(mine)).scalar_one() >= DAILY_EXTRACTIONS:
        record_refusal("extraction", get_settings().extraction_model)
        raise DailyLimitReached(USER_LIMIT_REACHED)
    attempt = ExtractionAttempt(user_id=user_id, attempted_at=datetime.now(UTC))
    db.add(attempt)
    await db.flush()
    return attempt


class IncompleteDocument(Exception):
    """Fields still unconfirmed or not found; the document can't be confirmed (HTTP 409)."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(", ".join(names))
        self.names = names


@dataclass(frozen=True)
class ConfirmedDocument:
    """A confirmed document's figures, the only form other features see (FR-009)."""

    id: uuid.UUID
    doc_type: DocType
    values: Mapping[FieldName, Decimal | str]
    # When it was uploaded: original file names aren't stored (R4), so other features name a
    # certificate by its type and this (005, auto-filled lines).
    uploaded_at: datetime | None = None
    # When it was (last) confirmed: 007's fingerprint notices a re-confirmation by this.
    confirmed_at: datetime | None = None


async def create_document(  # pylint: disable=too-many-arguments  # all keyword-only
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tax_year: str,
    doc_type: DocType,
    checked: CheckedFile,
    file_path: str,
) -> Document:
    """Record an uploaded, checked and stored file."""
    document = Document(
        user_id=user_id,
        doc_type=doc_type,
        tax_year=tax_year,
        file_path=file_path,
        media_type=checked.media_type,
        page_count=checked.page_count,
        status=DocStatus.UPLOADED,
        # The app's clock, not the database's now(), which is fixed for a whole transaction.
        created_at=datetime.now(UTC),
        fields=[],
    )
    db.add(document)
    await db.flush()
    return document


async def extract_document(
    db: AsyncSession, document: Document, extractor: Extractor, content: bytes
) -> Document:
    """Run extraction, normalise, apply the rules and save the fields (or the failure)."""
    document.status = DocStatus.EXTRACTING
    await db.flush()

    with ai_call("extraction", get_settings().extraction_model) as call:
        result = await extractor.extract(document.doc_type, content, document.media_type)
        record_usage(result.input_tokens, result.output_tokens)
        if result.limit_reached:
            call.outcome = "limit_reached"  # the free tier's limit (Google's 429)
        elif result.wrong_type:
            call.outcome = "check_failed"
        elif result.failure_reason is not None:
            call.outcome = "fallback"

    document.model = result.model
    if result.failure_reason is not None:
        document.status = DocStatus.FAILED
        document.failure_reason = result.failure_reason
        if result.wrong_type:
            await db.flush()
            raise WrongDocumentType(result.failure_reason)
    else:
        document.fields = build_fields(document.doc_type, document.tax_year, result.fields)
        document.status = DocStatus.NEEDS_REVIEW
        document.failure_reason = None
    await db.flush()
    return document


def build_fields(
    doc_type: DocType, tax_year: str, found: Mapping[str, ExtractedValue]
) -> list[ExtractedField]:
    """One field per name the type has (extra keys ignored, FR-003), checked by the rules."""
    fields = [_field(name, found.get(name.value)) for name in FIELDS_BY_TYPE[doc_type]]
    apply_rules(doc_type, tax_year, fields)
    return fields


def _field(name: FieldName, raw: ExtractedValue | None) -> ExtractedField:
    """A stored field from what the extractor reported (missing means "not found")."""
    found = raw is not None and raw.value is not None
    field = ExtractedField(
        name=name,
        confidence=Confidence(raw.confidence) if raw is not None else Confidence.LOW,
        source_page=raw.page if raw is not None and found else None,
        source_label=raw.label if raw is not None and found else None,
        user_edited=False,
        confirmed=False,
    )
    if raw is None or raw.value is None:
        return field
    if name is FieldName.TAX_YEAR:
        field.text_value = parse_tax_year(raw.value)
        return field
    try:
        field.amount = parse_amount(raw.value)
    except ValueError:
        field.confidence = Confidence.LOW
        # Generic on purpose: the misread text could be anything on the page (FR-003).
        field.rule_reason = f"{UNREADABLE} the printed amount."
    return field


def field_value(field: ExtractedField) -> Decimal | str | None:
    """The field's value: an amount, the tax year text, or None if not found."""
    return field.text_value if field.name is FieldName.TAX_YEAR else field.amount


def apply_rules(doc_type: DocType, tax_year: str, fields: list[ExtractedField]) -> None:
    """Lower each field that breaks a rule to low confidence, adding the reason (FR-005)."""
    reasons = check_rules(doc_type, {f.name: field_value(f) for f in fields}, tax_year)
    for field in fields:
        if field.name in reasons:
            field.confidence = Confidence.LOW
            existing = f"{field.rule_reason} " if field.rule_reason else ""
            field.rule_reason = existing + reasons[field.name]


def _recheck(document: Document) -> None:
    """Re-run the rules after an edit: old rule reasons go, unread-value notes on untouched
    fields stay. A field lowered earlier stays low, so the user still looks at it."""
    for field in document.fields:
        unread = field.rule_reason is not None and field.rule_reason.startswith(UNREADABLE)
        if not unread or field.user_edited:
            field.rule_reason = None
    apply_rules(document.doc_type, document.tax_year, list(document.fields))


def parse_user_value(name: FieldName, text: str) -> Decimal | str:
    """A value the user typed; raises ValueError with a message for anything invalid."""
    if name is FieldName.TAX_YEAR:
        year = parse_tax_year(text)
        if not is_tax_year(year):
            raise ValueError("Enter the tax year like 2025-26.")
        return year
    try:
        amount = parse_amount(text)
    except ValueError as exc:
        raise ValueError("Enter an amount in rupees, e.g. 1,800,000.") from exc
    if amount < 0:
        raise ValueError("The amount can't be negative.")
    return amount


async def edit_field(
    db: AsyncSession,
    document: Document,
    name: FieldName,
    *,
    value: str | None = None,
    confirmed: bool | None = None,
) -> ExtractedField:
    """Change and/or confirm one field (FR-007). An edit needs confirming again."""
    if document.status is not DocStatus.NEEDS_REVIEW:
        raise DocumentLocked(_locked_reason(document))
    field = next((f for f in document.fields if f.name is name), None)
    if field is None:
        raise FieldNotOnDocument(name.value)
    if value is not None:
        parsed = parse_user_value(name, value)
        if isinstance(parsed, Decimal):
            field.amount = parsed
        else:
            field.text_value = parsed
        field.user_edited = True
        field.confidence = Confidence.HIGH
        field.confirmed = False
        _recheck(document)
    if confirmed is not None:
        if confirmed:
            _check_confirmable(field)
        field.confirmed = confirmed
    await db.flush()
    return field


async def confirm_document(db: AsyncSession, document: Document) -> Document:
    """Confirm a document whose fields are all confirmed and filled in (FR-008)."""
    if document.status is not DocStatus.NEEDS_REVIEW:
        raise DocumentLocked(_locked_reason(document))
    order = FIELDS_BY_TYPE[document.doc_type]
    missing = [
        f.name.value
        for f in sorted(document.fields, key=lambda f: order.index(f.name))
        if not f.confirmed or field_value(f) is None
    ]
    if missing:
        raise IncompleteDocument(missing)
    for field in document.fields:
        _check_confirmable(field)
    year = next((f.text_value for f in document.fields if f.name is FieldName.TAX_YEAR), None)
    if year != document.tax_year:
        # FR-008: a certificate for another year must never be counted in the profile's year.
        raise DocumentLocked(
            f"This certificate is for {year}; your profile's tax year is {document.tax_year}. "
            "Correct the tax year if it was misread, or upload this year's certificate."
        )
    document.status = DocStatus.CONFIRMED
    document.confirmed_at = datetime.now(UTC)
    await db.flush()
    return document


def _check_confirmable(field: ExtractedField) -> None:
    """A field can be confirmed only with a value, and amounts only if not negative (FR-008)."""
    value = field_value(field)
    if value is None:
        raise ValueError("Enter a value before confirming this field.")
    if isinstance(value, Decimal) and value < 0:
        raise ValueError("The amount can't be negative. Correct it before confirming.")


def _locked_reason(document: Document) -> str:
    if document.status is DocStatus.CONFIRMED:
        return "This document is already confirmed."
    return "This document has no figures to review."


async def confirmed_documents(
    db: AsyncSession, user_id: uuid.UUID, tax_year: str
) -> list[ConfirmedDocument]:
    """The user's confirmed documents for the tax year and their figures (FR-009, R9).

    The only way other features read extracted figures; unconfirmed ones are never returned.
    Several confirmed documents of one type are all returned (FR-010a).
    """
    documents = await db.scalars(
        select(Document)
        .where(
            Document.user_id == user_id,
            Document.tax_year == tax_year,
            Document.status == DocStatus.CONFIRMED,
        )
        .order_by(Document.created_at)
    )
    return [
        ConfirmedDocument(
            id=document.id,
            doc_type=document.doc_type,
            uploaded_at=document.created_at,
            confirmed_at=document.confirmed_at,
            values={
                f.name: value for f in document.fields if (value := field_value(f)) is not None
            },
        )
        for document in documents
        # Defence in depth: the status alone isn't trusted if any field is unconfirmed.
        if all(f.confirmed for f in document.fields)
    ]


async def get_document(
    db: AsyncSession, user_id: uuid.UUID, document_id: uuid.UUID, *, for_update: bool = False
) -> Document | None:
    """The user's document, or None if it doesn't exist or belongs to someone else.

    `for_update` locks the row until the transaction ends, so an edit and a confirm of the
    same document can't interleave (a confirm could otherwise pass on a just-edited field).
    """
    query = select(Document).where(Document.id == document_id, Document.user_id == user_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await db.scalars(query)).one_or_none()


async def list_documents(db: AsyncSession, user_id: uuid.UUID) -> list[Document]:
    """The user's documents, newest first."""
    documents = await db.scalars(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc(), Document.id)
    )
    return list(documents)


async def retry_extraction(
    db: AsyncSession, document: Document, extractor: Extractor, storage: Storage
) -> Document:
    """Re-run a failed extraction on the stored file (bucket or disk, FR-018)."""
    if document.status is not DocStatus.FAILED:
        raise DocumentLocked("Only a failed extraction can be retried.")
    content = await storage.read(document.file_path)
    if content is None:
        document.failure_reason = (
            "The stored file is missing. Delete this document and upload it again."
        )
        await db.flush()
        return document
    # Counted only now that the AI will be called, and committed first so neither the limit's
    # lock nor this row's is held during the call (002 review M2, M3); then the row is locked
    # again and rechecked, since an edit or delete could have come in between.
    await use_extraction(db, document.user_id)
    await db.commit()
    await db.refresh(document, with_for_update=True)
    if document.status is not DocStatus.FAILED:
        raise DocumentLocked("Only a failed extraction can be retried.")
    return await extract_document(db, document, extractor, content)


async def delete_document(db: AsyncSession, document: Document) -> str:
    """Delete the document and its fields; returns where its file is, to remove after commit."""
    location = document.file_path
    await db.delete(document)
    await db.flush()
    return location
