"""FastAPI entry point. Routers from app/api/ are added here as we build them."""

from fastapi import FastAPI

app = FastAPI(title="AI Fitness Agent API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used by us now and by Render later."""
    return {"status": "ok"}
