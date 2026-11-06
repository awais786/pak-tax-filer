"""FastAPI application entry point (uvicorn app.main:app)."""

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.profile.router import router as profile_router

app = FastAPI(title="pak-tax-filer")
app.include_router(auth_router)
app.include_router(profile_router)


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


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: specs/001-repo-foundations/contracts/health.md (spec FR-003)."""
    return {"status": "ok"}
