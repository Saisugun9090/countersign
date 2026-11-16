"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Countersign")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}
