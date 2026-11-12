"""The guided run's API (feature 007, tasks T010, T015; contracts/workflow-api.md).

HTTP only: the service runs the steps and enforces the gate. Every endpoint needs a login and a
taxpayer profile (002's require_profile: 409 "Set up your profile first.").
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user, require_json
from app.auth.models import User
from app.db import get_db, get_sessionmaker
from app.profile.dependencies import require_profile
from app.profile.models import TaxpayerProfile
from app.rag.embed import Embedder
from app.rag.router import get_embedder
from app.settings import get_settings
from app.tax.router import tax_out
from app.workflow import service
from app.workflow.client import AgentClient, GeminiAgentClient
from app.workflow.models import Step, WorkflowRun
from app.workflow.state import InvalidTransition

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

Sessions = Callable[[], AbstractAsyncContextManager[AsyncSession]]

NO_RUN = service.NO_RUN
APPROVAL_NEEDED = "Approval needed."
_GATE_ONWARDS = (Step.GATE, Step.RESULT, Step.DONE)


def get_agent_client() -> AgentClient:
    """The agents' client the app uses (tests replace it with a FakeAgentClient)."""
    settings = get_settings()
    return GeminiAgentClient(
        api_key=settings.gemini_api_key,
        model=settings.workflow_model,
        effort=settings.workflow_effort,
    )


def get_tool_sessions() -> Sessions:
    """Sessions for the agents' tools, separate from the request's (tests use their own)."""
    return get_sessionmaker()


async def get_context(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    user: Annotated[User, Depends(current_user)],
    profile: Annotated[TaxpayerProfile, Depends(require_profile)],
    db: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[AgentClient, Depends(get_agent_client)],
    embedder: Annotated[Embedder, Depends(get_embedder)],
    tool_sessions: Annotated[Sessions, Depends(get_tool_sessions)],
) -> service.Context:
    """The request's user, profile, session and AI services, for the service."""
    return service.Context(
        db=db,
        user=user,
        profile=profile,
        client=client,
        embedder=embedder,
        tool_sessions=tool_sessions,
    )


Ctx = Annotated[service.Context, Depends(get_context)]


def run_out(run: WorkflowRun) -> dict[str, Any]:
    """The contract's run object."""
    outputs = run.step_outputs or {}
    return {
        "step": run.step.value,
        "tax_year": run.tax_year,
        "fingerprint": run.outputs_fingerprint,
        "document": outputs.get("document"),
        "validation": outputs.get("validation"),
        "research": outputs.get("research"),
        "inputs_changed": bool(outputs.get("inputs_changed", False)),
        "gate": outputs.get("gate") if run.step in _GATE_ONWARDS else None,
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "done_at": run.done_at.isoformat() if run.done_at else None,
    }


@router.get("")
async def read_run(ctx: Ctx) -> dict[str, Any]:
    """The current run, re-checked first if the inputs changed; 404 before the first start."""
    run = await service.get_run(ctx)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_RUN)
    return run_out(run)


@router.post("/start", dependencies=[Depends(require_json)])
async def start_run(ctx: Ctx) -> dict[str, Any]:
    """Start (or restart) the run: steps 1-3, then the gate or what's missing."""
    return run_out(await service.start(ctx))


class ApproveIn(BaseModel):
    """The run's fingerprint as the user saw it at the gate."""

    fingerprint: str


def _refused(error: InvalidTransition) -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, str(error))


@router.post("/approve", dependencies=[Depends(require_json)])
async def approve_run(body: ApproveIn, ctx: Ctx) -> dict[str, Any]:
    """Record approval at the gate; 409 away from it or if the inputs changed since shown."""
    try:
        return run_out(await service.approve(ctx, body.fingerprint))
    except service.NoRun as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_RUN) from error
    except InvalidTransition as error:
        raise _refused(error) from error


@router.post("/back", dependencies=[Depends(require_json)])
async def back_run(ctx: Ctx) -> dict[str, Any]:
    """Leave the gate for step 1."""
    try:
        return run_out(await service.back(ctx))
    except service.NoRun as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_RUN) from error
    except InvalidTransition as error:
        raise _refused(error) from error


@router.get("/result")
async def read_result(ctx: Ctx) -> dict[str, Any]:
    """004's result (exactly the Tax page's body) plus the research passages; 409 "Approval
    needed." unless approved for the current inputs."""
    found = await service.result(ctx)
    if found is None:
        raise HTTPException(status.HTTP_409_CONFLICT, APPROVAL_NEEDED)
    run, tax, _ = found
    research = (run.step_outputs or {}).get("research") or {}
    return {**tax_out(tax).model_dump(), "passages": research.get("passages", [])}


@router.post("/done", dependencies=[Depends(require_json)])
async def mark_done(ctx: Ctx) -> dict[str, Any]:
    """Mark the run done; 409 before its result."""
    try:
        return run_out(await service.mark_done(ctx))
    except service.NoRun as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_RUN) from error
    except InvalidTransition as error:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not at the result step.") from error
