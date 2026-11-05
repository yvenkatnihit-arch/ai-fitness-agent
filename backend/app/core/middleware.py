"""Per-request context: request ID, one access log line, and a safe 500 for unexpected errors.

Written as plain ASGI middleware (not BaseHTTPMiddleware) so it also works with streamed
responses, which the chat will use in Phase 7.

It sits INSIDE the CORS middleware, so even a 500 still carries CORS headers and the
browser shows our error message instead of a confusing "CORS error".
"""

import json
import logging
import re
import time
import uuid

from psycopg_pool import PoolTimeout

from app.core.logging import request_id_var

logger = logging.getLogger("app.request")

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
SERVER_ERROR = "Something went wrong on our side. Please try again."
BUSY = "The service is busy right now. Please try again in a moment."


class RequestContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        incoming = headers.get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        response = {"status": 500, "started": False}

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
                response["started"] = True
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except PoolTimeout:
            logger.warning("database pool exhausted")
            await self._json_error(send_with_id, response, 503, BUSY, request_id)
        except Exception:
            logger.exception("unhandled error")  # full traceback goes to logs only
            await self._json_error(send_with_id, response, 500, SERVER_ERROR, request_id)
        finally:
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],  # path only: query strings can carry personal data
                    "status": response["status"],
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
            request_id_var.reset(token)

    @staticmethod
    async def _json_error(send, response, status, detail, request_id):
        if response["started"]:
            return  # headers already sent; nothing more we can do for this response
        body = json.dumps({"detail": detail, "request_id": request_id}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        })
        await send({"type": "http.response.body", "body": body})
