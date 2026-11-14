"""FastAPI application entry point (uvicorn app.main:app)."""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth.router import router as auth_router
from app.documents.router import router as documents_router
from app.profile.router import router as profile_router
from app.rag.router import router as ask_router
from app.reports.router import router as reports_router
from app.workflow.router import router as workflow_router
from app.tax.router import router as tax_router
from app.telemetry.setup import configure as configure_telemetry
from app.wealth.router import router as wealth_router

app = FastAPI(title="pak-tax-filer")
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(documents_router)
app.include_router(tax_router)
app.include_router(wealth_router)
app.include_router(ask_router)
app.include_router(workflow_router)
app.include_router(reports_router)
# Request and database spans to the logs, for developers (feature 008, US3).
configure_telemetry(app)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's usual 422 reply, minus each rejected value (`input`).

    The default echoes what was sent, e.g. a malformed login's password; error messages must
    never carry secrets or personal data (.claude/rules/security.md). Field and reason stay.
    """
    errors = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


class HealthOut(BaseModel):
    """The health reply (declared, as every route's response is: docs/api-conventions.md)."""

    status: str


@app.get("/health")
def health() -> HealthOut:
    """Liveness check: specs/001-repo-foundations/contracts/health.md (spec FR-003)."""
    return HealthOut(status="ok")
