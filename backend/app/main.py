"""FastAPI entry point. Routers from app/api/ are added here as we build them."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import db
from app.api import me


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    db.close_pool()  # the pool opens lazily on first use; close it cleanly on shutdown


app = FastAPI(title="AI Fitness Agent API", version="0.1.0", lifespan=lifespan)
app.include_router(me.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: is the app process running? Never touches the database."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: can the app reach the database? 503 if not."""
    if db.ping():
        return JSONResponse({"status": "ok", "database": "ok"})
    return JSONResponse({"status": "unavailable", "database": "unreachable"}, status_code=503)
