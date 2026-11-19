"""The admin area's pages (feature 011, tasks T018, T025, T029; FR-006 to FR-014; research R5-R7).

Every view is read-only: nothing can be created, edited, deleted, exported or imported (FR-012),
and fields are listed explicitly, so no secret column is ever shown (FR-013). Opening an account's
details records one audit entry (FR-016); list pages record nothing.
"""

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from starlette.requests import Request
from starlette_admin import (
    BooleanField,
    ComputedField,
    CustomView,
    DateTimeField,
    EnumField,
    GridWidget,
    RequestAction,
    StatWidget,
    StringField,
    TableWidget,
)
from starlette_admin.actions import row_action
from starlette_admin.contrib.sqla import ModelView
from starlette_admin.exceptions import ActionFailed
from starlette_admin.widgets import BaseWidget

from app.admin import actions, audit
from app.admin.models import AdminAuditEntry
from app.admin.overview import Limit, account_overview, dashboard_counts
from app.auth.models import User
from app.documents.models import DocStatus, DocType, Document
from app.documents.storage import Storage
from app.rag.models import CorpusDocument, DocumentKind, Passage
from app.telemetry.store import telemetry_summary


ACCOUNT_ACTIONS = frozenset(
    {"disable", "enable", "delete_account", "sign_out_everywhere", "reset_reading_limit"}
)


class ReadOnlyView(ModelView):
    """A model view with nothing to create, edit, delete, export or import (FR-012)."""

    def can_create(self, request: Request) -> bool:
        return False

    def can_edit(self, request: Request) -> bool:
        return False

    def can_delete(self, request: Request) -> bool:
        return False

    def can_export(self, request: Request) -> bool:
        return False

    def can_import(self, request: Request) -> bool:
        return False


async def _email(request: Request, user_id: Any) -> str:
    """An account's email while it exists, else its id (FR-018)."""
    email = (
        await request.state.session.execute(select(User.email).where(User.id == user_id))
    ).scalar_one_or_none()
    return email or str(user_id)


class AccountView(ReadOnlyView):
    """Accounts: email, created, admin, disabled; search by email; the overview on the detail;
    the four actions on taxpayer accounts (T025)."""

    def __init__(self, storage: Callable[[], Storage], **kwargs: Any) -> None:
        super().__init__(User, **kwargs)
        self._storage = storage

    fields = [
        StringField("email"),
        DateTimeField("created_at"),
        BooleanField("is_admin"),
        DateTimeField("disabled_at"),
    ]
    searchable_fields = ["email"]
    fields_default_sort = [("created_at", True)]
    detail_template = "account_detail.html"

    async def find_by_pk(self, request: Request, pk: Any) -> Any:
        """The account; on its detail page, also its overview and one audit entry (R6)."""
        account = await super().find_by_pk(request, pk)
        if account is not None and request.state.action == RequestAction.DETAIL:
            db = request.state.session
            request.state.overview = await account_overview(db, account)
            await audit.record(db, request.state.admin_id, "view_account", account.id)
        return account

    async def is_row_action_allowed_for_obj(self, request: Request, name: str, obj: Any) -> bool:
        """No account action on an admin account; Disable or Re-enable by state."""
        if name in ACCOUNT_ACTIONS and obj.is_admin:
            return False
        if name == "disable":
            return obj.disabled_at is None
        if name == "enable":
            return obj.disabled_at is not None
        return await super().is_row_action_allowed_for_obj(request, name, obj)

    async def _act(self, request: Request, pk: Any, action: Callable[..., Awaitable[None]]) -> None:
        try:
            await action(request.state.session, request.state.admin_id, uuid.UUID(str(pk)))
        except (actions.AccountGone, actions.TargetIsAdmin, actions.StorageDown) as refused:
            raise ActionFailed(str(refused)) from refused

    @row_action(
        name="disable",
        text="Disable",
        confirmation="Disable this account? The user is signed out and can't sign in.",
        submit_btn_class="btn-danger",
    )
    async def disable_row(self, request: Request, pk: Any) -> str:
        """FR-014(a)."""
        await self._act(request, pk, actions.disable_account)
        return "Account disabled."

    @row_action(name="enable", text="Re-enable", confirmation="Re-enable this account?")
    async def enable_row(self, request: Request, pk: Any) -> str:
        """FR-014(b)."""
        await self._act(request, pk, actions.enable_account)
        return "Account re-enabled."

    @row_action(
        name="delete_account",
        text="Delete account",
        confirmation="Delete this account and all its data? This can't be undone.",
        submit_btn_class="btn-danger",
    )
    async def delete_row(self, request: Request, pk: Any) -> str:
        """FR-014(c): files first, then the account."""
        storage = self._storage()

        async def delete(db: Any, admin_id: uuid.UUID, user_id: uuid.UUID) -> None:
            await actions.delete_account(db, storage, admin_id, user_id)

        await self._act(request, pk, delete)
        return "Account deleted."

    @row_action(
        name="sign_out_everywhere",
        text="Sign out everywhere",
        confirmation="Sign this user out on every device?",
    )
    async def sign_out_row(self, request: Request, pk: Any) -> str:
        """FR-014(d)."""
        await self._act(request, pk, actions.sign_out_everywhere)
        return "Signed out everywhere."

    @row_action(
        name="reset_reading_limit",
        text="Reset reading limit",
        confirmation="Clear this user's document readings from the last 24 hours?",
    )
    async def reset_row(self, request: Request, pk: Any) -> str:
        """FR-014(e)."""
        await self._act(request, pk, actions.reset_reading_limit)
        return "Reading limit reset."


class OwnerEmail(ComputedField):
    """The document's owner, by email."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.user_id)


class DocumentView(ReadOnlyView):
    """Documents: type, status, tax year, uploaded, owner; never the file, no detail page."""

    fields = [
        EnumField("doc_type", enum=DocType),
        EnumField("status", enum=DocStatus),
        StringField("tax_year"),
        DateTimeField("created_at"),
        OwnerEmail("owner"),
    ]
    fields_default_sort = [("created_at", True)]

    def can_view_detail(self, request: Request) -> bool:
        return False


class PassageCount(ComputedField):
    """How many passages a corpus document has."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        count = (
            await request.state.session.execute(
                select(func.count()).select_from(Passage).where(Passage.document_id == obj.id)
            )
        ).scalar_one()
        return str(count)


class CorpusDocumentView(ReadOnlyView):
    """The law library: each FBR document and its passage count (FR-011)."""

    fields = [
        StringField("title"),
        EnumField("kind", enum=DocumentKind),
        DateTimeField("built_at"),
        PassageCount("passages"),
    ]


class AdminEmail(ComputedField):
    """The admin who acted, by email (or id once deleted)."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.admin_id)


class AccountEmail(ComputedField):
    """The account acted on, by email (or id once deleted)."""

    async def parse_obj(self, request: Request, obj: Any) -> str:
        return await _email(request, obj.target_user_id)


class AuditLogView(ReadOnlyView):
    """The audit log, newest first (FR-018)."""

    fields = [
        DateTimeField("at"),
        AdminEmail("admin"),
        StringField("action"),
        AccountEmail("account"),
    ]
    fields_default_sort = [("at", True)]

    def can_view_detail(self, request: Request) -> bool:
        return False


def _shown(limit: Limit) -> str:
    return f"{limit.used} of {limit.limit}"


async def dashboard(request: Request) -> BaseWidget:
    """The dashboard's stat tiles, from one read of the counts (FR-006)."""
    counts = await dashboard_counts(request.state.session)
    runs = ", ".join(f"{step}: {n}" for step, n in sorted(counts.runs_per_step.items())) or "none"
    tiles: list[tuple[str, str]] = [
        ("Taxpayer accounts", str(counts.taxpayers)),
        ("Profiles set up", str(counts.profiles)),
        ("Documents uploaded", str(counts.documents.get("uploaded", 0))),
        ("Documents confirmed", str(counts.documents.get("confirmed", 0))),
        ("Documents failed", str(counts.documents.get("failed", 0))),
        ("Guided runs by step", runs),
        ("Document readings today", _shown(counts.readings_app)),
        ("Most readings by one user today", _shown(counts.readings_busiest_user)),
        ("Ask questions today", _shown(counts.questions_app)),
        ("Most questions by one user this hour", _shown(counts.questions_busiest_user_hour)),
    ]
    return GridWidget(children=[StatWidget(title, _constant(value)) for title, value in tiles])


def _constant(value: str) -> Any:
    async def callback(_request: Request) -> str:
        return value

    return callback


def _rows(rows: list[list[Any]]) -> Any:
    async def callback(_request: Request) -> list[list[Any]]:
        return rows

    return callback


async def telemetry(request: Request) -> BaseWidget:
    """The telemetry page: the last 30 days of requests and AI calls (FR-022)."""
    summary = await telemetry_summary(request.state.session, datetime.now(UTC))
    tables: list[tuple[str, list[str], list[list[Any]]]] = [
        (
            "Requests per day",
            ["Day", "Requests"],
            [[str(d), n] for d, n in summary.requests_per_day],
        ),
        (
            "Slowest pages",
            ["Page", "Requests", "Median ms", "95th percentile ms"],
            [[r.route, r.requests, r.median_ms, r.p95_ms] for r in summary.slowest_routes],
        ),
        ("AI calls", ["Feature", "Outcome", "Calls"], [list(c) for c in summary.ai_calls]),
        ("AI call duration", ["Feature", "Median ms"], [list(d) for d in summary.ai_duration]),
        (
            "Tokens per day",
            ["Day", "Input tokens", "Output tokens"],
            [[str(d), i, o] for d, i, o in summary.tokens_per_day],
        ),
    ]
    return GridWidget(
        children=[
            StatWidget(
                "Server errors (last 30 days)",
                _constant(f"{summary.server_error_share:.1f}% of requests"),
            ),
            *(TableWidget(title, columns, _rows(rows)) for title, columns, rows in tables),
        ]
    )


def telemetry_view() -> CustomView:
    """The telemetry page at /admin/telemetry."""
    return CustomView(
        menu_label="Telemetry",
        icon="fa fa-chart-line",
        path="/telemetry",
        route_name="telemetry",
        widget=telemetry,
    )


def dashboard_view() -> CustomView:
    """The admin index page."""
    return CustomView(menu_label="Dashboard", icon="fa fa-gauge", widget=dashboard)


def model_views(storage: Callable[[], Storage]) -> list[ModelView]:
    """Every model view, in menu order; `storage` gives the uploaded files' storage."""
    return [
        AccountView(storage, key="account", menu_label="Accounts", icon="fa fa-users"),
        DocumentView(Document, key="document", menu_label="Documents", icon="fa fa-file"),
        CorpusDocumentView(
            CorpusDocument, key="corpus-document", menu_label="Law library", icon="fa fa-book"
        ),
        AuditLogView(AdminAuditEntry, key="audit-log", menu_label="Audit log", icon="fa fa-list"),
    ]
