"""FastAPI application entry point (uvicorn app.main:app)."""

from fastapi import FastAPI

app = FastAPI(title="pak-tax-filer")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check: specs/001-repo-foundations/contracts/health.md (spec FR-003)."""
    return {"status": "ok"}
