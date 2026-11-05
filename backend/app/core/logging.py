"""Structured logs: one JSON object per line on stdout (Render shows these in its log view).

Every line carries the current request_id, so all lines for one request can be found together.
Never log request bodies or Authorization headers: they can contain health data or tokens.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

# Set per request by RequestContextMiddleware; "-" outside a request (startup, scripts).
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Standard LogRecord attributes; anything else passed via `extra=` is added to the JSON.
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        entry.update({k: v for k, v in vars(record).items() if k not in _RESERVED})
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn prints its own access line per request; ours (with request_id) replaces it.
    logging.getLogger("uvicorn.access").disabled = True
