"""FastAPI entry point. Routers from app/api/ are added here as we build them."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import db
from app.api import chat, exercises, foods, meals, me, onboarding, plans, profile, splits, targets, training
from app.core.config import get_app_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestContextMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(get_app_settings().log_level)
    yield
    db.close_pool()  # the pool opens lazily on first use; close it cleanly on shutdown


app = FastAPI(title="AI Fitness Agent API", version="0.1.0", lifespan=lifespan)
register_error_handlers(app)

# Middleware added LAST runs FIRST. So CORS wraps everything, including our safe-500 handler.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_app_settings().cors_origins,  # exact frontend URLs only, from .env
    allow_credentials=False,                     # we use Bearer tokens, not cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],             # so the frontend can show it in error messages
    max_age=600,                                 # browsers may cache the preflight answer for 10 min
)

app.include_router(me.router)
app.include_router(onboarding.router)
app.include_router(targets.router)
app.include_router(foods.router)
app.include_router(meals.router)
app.include_router(exercises.router)
app.include_router(splits.router)
app.include_router(plans.router)
app.include_router(chat.router)
app.include_router(profile.router)
app.include_router(training.router)


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
