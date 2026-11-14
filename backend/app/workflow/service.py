"""Starting, resuming and advancing a guided run (feature 007, tasks T010, T015, T019; research
R1-R3, R9).

Steps 1-3 run in one go: on start, and whenever the inputs' fingerprint differs from the one the
step outputs were made for (a certificate added, deleted or re-confirmed, or the profile
changed). Each such run counts as one question against 006's limits; past a limit the steps use
their plain results. Re-running clears any approval, so the result is only ever shown for inputs
the user approved (Principle III). The tax result itself is never stored.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.documents.service import ConfirmedDocument, confirmed_documents
from app.profile.models import TaxpayerProfile
from app.rag.embed import Embedder
from app.rag.service import use_question
from app.tax.engine import TaxResult, calculate
from app.tax.rates import rates_for
from app.tax.service import tax_inputs_from
from app.workflow.agents import document_step, research_step, validation_step
from app.workflow.client import AgentClient
from app.workflow.fingerprint import fingerprint
from app.workflow.models import Step, WorkflowRun
from app.workflow.state import Event, InvalidTransition, next_step, result_allowed
from app.workflow.tools import Toolbox

AGENT_STEPS = ("document", "validation", "research")


@dataclass(frozen=True)
class Context:
    """What a run needs from the request: the user, their profile and the AI services."""

    db: AsyncSession
    user: User
    profile: TaxpayerProfile
    client: AgentClient
    embedder: Embedder
    # Sessions for the agents' tools, separate from the request's (backend review M3).
    tool_sessions: Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def get_run(ctx: Context) -> WorkflowRun | None:
    """The user's run for the profile's tax year, re-running steps 1-3 first if the inputs
    changed since they ran; None if no run was started."""
    run, _ = await _current(ctx)
    return run


async def _current(ctx: Context) -> tuple[WorkflowRun | None, list[ConfirmedDocument]]:
    """The run, brought up to date with the inputs, and the one read of the certificates it is
    now up to date with: callers check the gate and calculate from this same read, so nothing
    confirmed in between can reach an approved result (backend review H1)."""
    run = await _find(ctx)
    documents = await confirmed_documents(ctx.db, ctx.user.id, ctx.profile.tax_year)
    if run is not None and run.outputs_fingerprint != _fingerprint(ctx, documents):
        # Says so on the page if an approval is being cleared, until approve or start (FR-013).
        after_approval = run.approved_at is not None or bool(
            (run.step_outputs or {}).get("inputs_changed")
        )
        await _run_steps(ctx, run, documents, Event.INPUTS_CHANGED, after_approval=after_approval)
    return run, documents


def _fingerprint(ctx: Context, documents: list[ConfirmedDocument]) -> str:
    return fingerprint(documents, ctx.profile.tax_year, ctx.profile.on_atl)


async def start(ctx: Context) -> WorkflowRun:
    """Start a run, or restart the existing one (still one row per user and year)."""
    now = datetime.now(UTC)
    # One row even if two tabs start at once (unique on user and tax year).
    await ctx.db.execute(
        insert(WorkflowRun)
        .values(
            user_id=ctx.user.id,
            tax_year=ctx.profile.tax_year,
            step=Step.DOCUMENT,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_workflow_runs_user_year")
    )
    run = await _find(ctx)
    assert run is not None  # just inserted, or already there
    documents = await confirmed_documents(ctx.db, ctx.user.id, ctx.profile.tax_year)
    await _run_steps(ctx, run, documents, Event.START)
    return run


async def _find(ctx: Context, *, lock: bool = False) -> WorkflowRun | None:
    """The run; with `lock`, re-read and locked until the transaction ends."""
    query = select(WorkflowRun).where(
        WorkflowRun.user_id == ctx.user.id, WorkflowRun.tax_year == ctx.profile.tax_year
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return (await ctx.db.execute(query)).scalar_one_or_none()


async def _run_steps(
    ctx: Context,
    run: WorkflowRun,
    documents: list[ConfirmedDocument],
    event: Event,
    *,
    after_approval: bool = False,
) -> None:
    """Run the document, validation and research steps on these inputs (one read)."""
    await _find(ctx, lock=True)  # re-read under a lock: a concurrent approval can't survive
    run.step = next_step(run.step, event)
    run.approved_at = run.approved_fingerprint = run.done_at = None
    # Cleared before anything can fail: until this run finishes, no approval can match it and
    # the next request re-runs it (backend review M2).
    run.outputs_fingerprint = None
    # Counted (and committed) before any AI is used, under 006's lock (research R9).
    use_ai = await use_question(ctx.db, ctx.user.id) is None
    await ctx.db.commit()

    tools = Toolbox(
        sessions=ctx.tool_sessions,
        user_id=ctx.user.id,
        profile_tax_year=ctx.profile.tax_year,
        embedder=ctx.embedder,
    )
    outputs: dict[str, Any] = {"document": await document_step(ctx.client, tools, use_ai=use_ai)}
    if outputs["document"]["missing"]:
        run.step = next_step(run.step, Event.MISSING_SALARY)
    else:
        outputs["validation"] = await validation_step(ctx.client, tools, documents, use_ai=use_ai)
        outputs["research"] = await research_step(ctx.client, tools, documents, use_ai=use_ai)
        outputs["gate"] = _gate(ctx, documents)
        for _ in AGENT_STEPS:
            run.step = next_step(run.step, Event.STEPS_OK)
    # True when this re-run cleared an approval: the page asks for a fresh one (T020).
    outputs["inputs_changed"] = after_approval
    run.step_outputs = outputs
    run.outputs_fingerprint = _fingerprint(ctx, documents)
    run.updated_at = datetime.now(UTC)
    await ctx.db.commit()


def _gate(ctx: Context, documents: list[ConfirmedDocument]) -> dict[str, Any]:
    """What the gate shows before approval, from the same read as the run's fingerprint: the
    confirmed figures the calculation would use (summed as 004 sums them) and the ATL status
    (FR-008)."""
    inputs = tax_inputs_from(documents, ctx.profile.tax_year, ctx.profile.on_atl)
    return {
        "figures": {
            "taxable_salary": _money(inputs.taxable_salary),
            "tax_deducted": _money(inputs.tax_deducted),
            "gross_profit": _money(inputs.gross_profit),
            "tax_withheld": _money(inputs.tax_withheld),
        },
        "on_atl": ctx.profile.on_atl,
    }


def _money(amount: Decimal) -> str:
    """Always two decimals ("1800000.00"), whether the amount was cached or read back."""
    return str(amount.quantize(Decimal("0.01")))


STALE = "Your inputs changed; please review and approve again."
NO_RUN = "No guided run yet."


class NoRun(Exception):
    """There is no run to act on (404, as GET answers before the first start)."""


async def approve(ctx: Context, seen: str) -> WorkflowRun:
    """Record the user's approval at the gate for the inputs they saw (`seen`, the run's
    fingerprint when shown). The run's row is locked, so two approvals together record one."""
    run = await _locked(ctx)  # steps 1-3 re-run first if the inputs changed
    if run is None:
        raise NoRun(NO_RUN)
    if seen != run.outputs_fingerprint:
        raise InvalidTransition(STALE)
    run.step = next_step(run.step, Event.APPROVE)
    run.approved_at = run.updated_at = datetime.now(UTC)
    run.approved_fingerprint = run.outputs_fingerprint
    run.step_outputs = {**run.step_outputs, "inputs_changed": False}
    await ctx.db.commit()
    return run


async def back(ctx: Context) -> WorkflowRun:
    """Leave the gate for step 1; a new approval is needed after the next start."""
    run = await _locked(ctx)
    if run is None:
        raise NoRun(NO_RUN)
    run.step = next_step(run.step, Event.BACK)
    run.approved_at = run.approved_fingerprint = None
    run.updated_at = datetime.now(UTC)
    await ctx.db.commit()
    return run


async def mark_done(ctx: Context) -> WorkflowRun:
    """Mark the run done; only at the result, with a current approval (FR-014)."""
    run = await get_run(ctx)
    if run is None:
        raise NoRun(NO_RUN)
    run.step = next_step(
        run.step,
        Event.MARK_DONE,
        approved=run.approved_fingerprint,
        current=run.outputs_fingerprint,
    )
    run.done_at = run.updated_at = datetime.now(UTC)
    await ctx.db.commit()
    return run


async def result(
    ctx: Context,
) -> tuple[WorkflowRun, TaxResult, list[ConfirmedDocument]] | None:
    """004's result for the run's inputs, or None without an approval for exactly them. The
    check and the calculation use one read of the certificates (backend review H1). Never
    stored: recalculated from the confirmed certificates on every request (as 004)."""
    run, documents = await _current(ctx)  # re-runs steps 1-3 (clearing any approval) if changed
    if run is None or not result_allowed(
        run.step, run.approved_fingerprint, _fingerprint(ctx, documents)
    ):
        return None
    inputs = tax_inputs_from(documents, ctx.profile.tax_year, ctx.profile.on_atl)
    return run, calculate(inputs, rates_for(ctx.profile.tax_year)), documents


async def _locked(ctx: Context) -> WorkflowRun | None:
    """The run, re-checked against the inputs, then locked until the transaction ends."""
    if await get_run(ctx) is None:
        return None
    return await _find(ctx, lock=True)
