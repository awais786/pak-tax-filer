"""/api/documents (feature 003, tasks T014, T018, T022).

Contract: specs/003-document-extraction/contracts/documents-api.md. Every endpoint is the
owner's only: other users' documents are 404, never 403 (docs/api-conventions.md).
"""

import uuid
from datetime import datetime
from typing import Annotated

import anyio
from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db
from app.documents.extraction.client import Extractor, GeminiExtractor
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
from app.documents.service import (
    DailyLimitReached,
    DocumentLocked,
    FieldNotOnDocument,
    IncompleteDocument,
    WrongDocumentType,
    confirm_document,
    create_document,
    delete_document,
    edit_field,
    extract_document,
    field_value,
    get_document,
    list_documents,
    retry_extraction,
    use_extraction,
)
from app.documents.storage import Storage, StorageUnavailable
from app.documents.uploads import MAX_BYTES, UploadRefused, check_file
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.settings import get_settings

router = APIRouter(prefix="/api/documents", tags=["documents"])

NOT_FOUND = "Document not found."


def get_extractor() -> Extractor:
    """The extractor the app uses (tests replace it with a FakeExtractor)."""
    settings = get_settings()
    return GeminiExtractor(
        api_key=settings.gemini_api_key,
        model=settings.extraction_model,
        effort=settings.extraction_effort,
    )


def get_storage() -> Storage:
    """Where uploaded files are kept: the private bucket if configured, else the disk (FR-018).
    Tests use a temporary folder."""
    settings = get_settings()
    return Storage(settings.upload_dir, settings.upload_bucket)


StorageDep = Annotated[Storage, Depends(get_storage)]


CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


class FieldOut(BaseModel):
    """One extracted figure as the review page shows it."""

    name: FieldName
    # A decimal string for amounts, "2025-26" for tax_year, null if not found.
    value: str | None
    confidence: Confidence
    source_page: int | None
    source_label: str | None
    rule_reason: str | None
    user_edited: bool
    confirmed: bool


class DocumentSummary(BaseModel):
    """A document in the list, without its figures."""

    id: uuid.UUID
    doc_type: DocType
    tax_year: str
    status: DocStatus
    failure_reason: str | None
    # application/pdf, image/jpeg or image/png: how the review page shows the original.
    media_type: str
    page_count: int
    created_at: datetime
    confirmed_at: datetime | None


class DocumentOut(DocumentSummary):
    """A document and its fields (contract "Document object")."""

    fields: list[FieldOut]


class FieldEdit(BaseModel):
    """PATCH body: a new value, a confirmation, or both. Unknown keys are refused."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    confirmed: StrictBool | None = None


def field_out(field: ExtractedField) -> FieldOut:
    """The API form of a field; amounts as decimal strings, never floats."""
    value = field_value(field)
    return FieldOut(
        name=field.name,
        value=None if value is None else str(value),
        confidence=field.confidence,
        source_page=field.source_page,
        source_label=field.source_label,
        rule_reason=field.rule_reason,
        user_edited=field.user_edited,
        confirmed=field.confirmed,
    )


def document_out(document: Document) -> DocumentOut:
    """The API form of a document, its fields in the type's display order."""
    order = FIELDS_BY_TYPE[document.doc_type]
    fields = sorted(document.fields, key=lambda field: order.index(field.name))
    return DocumentOut(
        id=document.id,
        doc_type=document.doc_type,
        tax_year=document.tax_year,
        status=document.status,
        failure_reason=document.failure_reason,
        media_type=document.media_type,
        page_count=document.page_count,
        created_at=document.created_at,
        confirmed_at=document.confirmed_at,
        fields=[field_out(field) for field in fields],
    )


async def owned_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Document:
    """The caller's document, or 404 if it doesn't exist or isn't theirs."""
    document = await get_document(db, user.id, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return document


async def locked_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Document:
    """The caller's document, row-locked for a state change; 404 if it isn't theirs."""
    document = await get_document(db, user.id, document_id, for_update=True)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return document


OwnedDocument = Annotated[Document, Depends(owned_document)]
LockedDocument = Annotated[Document, Depends(locked_document)]
ExtractorDep = Annotated[Extractor, Depends(get_extractor)]


def _summary(document: Document) -> DocumentSummary:
    return DocumentSummary.model_validate(document_out(document).model_dump(exclude={"fields"}))


async def _use_extraction(db: AsyncSession, user_id: uuid.UUID) -> ExtractionAttempt:
    """Count one AI call for the user, or answer 429 once the day's are used (FR-017)."""
    try:
        return await use_extraction(db, user_id)
    except DailyLimitReached as limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(limit)) from limit


def _unavailable(error: StorageUnavailable) -> HTTPException:
    """Google Cloud Storage refused or failed: 503, saying only "try again later" (FR-018)."""
    return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))


async def _remove_quietly(storage: Storage, location: str) -> None:
    """Remove a file that nothing records any more. Shielded, so a cancelled request still
    removes it, and never raising, so the original error is the one reported (storage review)."""
    with anyio.CancelScope(shield=True):
        try:
            await storage.delete(location)
        except StorageUnavailable:
            pass  # already logged by type; the file stays, unrecorded, in the private bucket


@router.get("")
async def read_documents(user: CurrentUser, db: DbSession) -> list[DocumentSummary]:
    """The caller's documents, newest first, without their figures."""
    return [_summary(document) for document in await list_documents(db, user.id)]


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_document(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    user: CurrentUser,
    profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    db: DbSession,
    extractor: ExtractorDep,
    storage: StorageDep,
    file: UploadFile,
    doc_type: Annotated[DocType, Form()],
) -> DocumentOut:
    """Check, store and extract a certificate; the tax year is the profile's (feature 002)."""
    content = await file.read(MAX_BYTES + 1)
    try:
        checked = check_file(file.filename or "", content)
    except UploadRefused as refused:
        raise HTTPException(refused.status_code, refused.detail) from refused
    attempt = await _use_extraction(db, user.id)
    # Committed now, so the attempt counts even if extraction is refused below (FR-017).
    await db.commit()
    try:
        location = await storage.save(user.id, content, checked.extension, checked.media_type)
    except StorageUnavailable as unavailable:
        # The AI was never called, so this mustn't cost one of the day's extractions.
        await db.delete(attempt)
        await db.commit()
        raise _unavailable(unavailable) from unavailable
    try:
        document = await create_document(
            db,
            user_id=user.id,
            tax_year=profile.tax_year,
            doc_type=doc_type,
            checked=checked,
            file_path=location,
        )
        try:
            await extract_document(db, document, extractor, content, attempt)
        except WrongDocumentType as wrong:
            # Refused, not kept (FR-005a): retrying the same type would only fail again.
            await db.delete(document)
            await db.flush()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(wrong)) from wrong
        await db.commit()
    except BaseException:
        # Nothing records the file now, so delete could never remove it: remove it here.
        await _remove_quietly(storage, location)
        raise
    return document_out(document)


@router.get("/{document_id}")
async def read_document(document: OwnedDocument) -> DocumentOut:
    """One of the caller's documents with its fields."""
    return document_out(document)


@router.get("/{document_id}/file")
async def read_document_file(document: OwnedDocument, storage: StorageDep) -> Response:
    """The original file, for the review page: only through this owner check, never a public
    link to the bucket (FR-018)."""
    try:
        content = await storage.read(document.file_path)
    except StorageUnavailable as unavailable:
        raise _unavailable(unavailable) from unavailable
    if content is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The stored file is missing.")
    return Response(content, media_type=document.media_type)


@router.patch("/{document_id}/fields/{name}", dependencies=[Depends(require_json)])
async def update_field(
    document: LockedDocument, name: str, body: FieldEdit, db: DbSession
) -> FieldOut:
    """Edit and/or confirm one field; the rules run again after an edit."""
    try:
        field_name = FieldName(name)
    except ValueError as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found.") from unknown
    try:
        field = await edit_field(
            db, document, field_name, value=body.value, confirmed=body.confirmed
        )
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    except FieldNotOnDocument as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found.") from missing
    except ValueError as invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    await db.commit()
    return field_out(field)


@router.post("/{document_id}/confirm", dependencies=[Depends(require_json)])
async def confirm(document: LockedDocument, db: DbSession) -> DocumentOut:
    """Confirm the document; only then can other features use its figures."""
    try:
        await confirm_document(db, document)
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    except IncompleteDocument as incomplete:
        detail = "Confirm or fill in these fields first: " + ", ".join(incomplete.names) + "."
        raise HTTPException(status.HTTP_409_CONFLICT, detail) from incomplete
    await db.commit()
    return document_out(document)


@router.post("/{document_id}/retry", dependencies=[Depends(require_json)])
async def retry(
    document: LockedDocument, db: DbSession, extractor: ExtractorDep, storage: StorageDep
) -> DocumentOut:
    """Re-run a failed extraction (counted towards the daily limits, FR-017)."""
    try:
        await retry_extraction(db, document, extractor, storage)
    except DailyLimitReached as limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(limit)) from limit
    except StorageUnavailable as unavailable:
        raise _unavailable(unavailable) from unavailable
    except DocumentLocked as locked:
        raise HTTPException(status.HTTP_409_CONFLICT, str(locked)) from locked
    except WrongDocumentType:
        pass  # The document already exists: it stays failed, with the reason.
    await db.commit()
    return document_out(document)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_json)],
)
async def delete(document: LockedDocument, db: DbSession, storage: StorageDep) -> Response:
    """Delete the document, its fields and its stored file."""
    location = await delete_document(db, document)
    await db.commit()
    # The document is gone; a file that can't be removed now mustn't turn that into an error.
    await _remove_quietly(storage, location)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
