# Backend image for Render (D-033). Build from the backend/ folder:
#   docker build -t ai-fitness-backend .
# Secrets are NOT in the image: pass them at run time (--env-file locally, dashboard on Render).

# --- Stage 1: install dependencies exactly as locked in uv.lock --------------------------
FROM python:3.14.7-slim AS builder

# uv pinned to a release at least ~2 weeks old (D-030).
COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, code later: Docker caches this layer, so code-only changes rebuild fast.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# --- Stage 2: the small image that actually runs ------------------------------------------
FROM python:3.14.7-slim

# Run as an ordinary user, not root.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_ENV=production

USER appuser

# Render sets PORT (usually 10000); 8000 locally.
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/health', timeout=4)"

# --proxy-headers: Render sits in front of the app, so trust its X-Forwarded-* headers.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
