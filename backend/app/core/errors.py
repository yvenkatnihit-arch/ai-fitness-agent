"""One error shape for the whole API: {"detail": "<message safe to show>", "request_id": "..."}.

Validation errors also list each problem field. They never echo the submitted values back,
because those can be health data.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import request_id_var

CHECK_FIELDS = "Please check the highlighted fields."


def _field_name(location: tuple) -> str:
    """('body', 'screening', 0) -> 'screening.0'; the leading 'body'/'query' isn't useful to users."""
    parts = [str(p) for p in location if p not in ("body", "query", "path")]
    return ".".join(parts) or "request"


def _clean_message(message: str) -> str:
    # Pydantic prefixes our own validator messages with "Value error, ".
    return message.removeprefix("Value error, ")


async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"field": _field_name(e["loc"]), "message": _clean_message(e["msg"])} for e in exc.errors()]
    return JSONResponse(
        {"detail": CHECK_FIELDS, "errors": errors, "request_id": request_id_var.get()}, status_code=422
    )


async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        {"detail": exc.detail, "request_id": request_id_var.get()},
        status_code=exc.status_code,
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_error)
    app.add_exception_handler(HTTPException, http_error)
