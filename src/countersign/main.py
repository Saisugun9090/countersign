"""FastAPI application entry point."""

from fastapi import FastAPI

from countersign.config import get_settings

app = FastAPI(title="Countersign")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}
