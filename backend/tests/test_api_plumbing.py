"""CORS, request IDs, error format, and logging. No database needed."""

import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from app.core.auth import CurrentUser, get_current_user
from app.core.logging import JsonFormatter, request_id_var
from app.core.middleware import BUSY, SERVER_ERROR
from app.main import app

ALLOWED = "http://localhost:5173"  # the default CORS_ORIGINS
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def broken_me():
    """Make /me crash with a given exception, to test the safety net."""

    def _break(error):
        def boom():
            raise error

        app.dependency_overrides[get_current_user] = boom

    yield _break
    app.dependency_overrides.clear()


# --- CORS ---

def test_preflight_from_the_frontend_is_allowed():
    response = client.options("/me", headers={
        "Origin": ALLOWED,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "authorization",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_other_websites_get_no_cors_permission():
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_headers_survive_a_crash(broken_me):
    broken_me(RuntimeError("boom"))
    response = client.get("/me", headers={"Origin": ALLOWED})
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == ALLOWED  # browser can read our message


# --- Request IDs ---

def test_every_response_has_a_request_id():
    assert len(client.get("/health").headers["x-request-id"]) >= 8


def test_a_valid_incoming_request_id_is_kept():
    rid = "frontend-1234abcd"
    assert client.get("/health", headers={"X-Request-ID": rid}).headers["x-request-id"] == rid


@pytest.mark.parametrize("bad", ["short", "has spaces in it!", "x" * 65, "<script>alert(1)</script>"])
def test_a_strange_incoming_request_id_is_replaced(bad):
    assert client.get("/health", headers={"X-Request-ID": bad}).headers["x-request-id"] != bad


# --- Error format ---

def test_unexpected_errors_never_leak_details(broken_me):
    broken_me(RuntimeError("password=hunter2 at line 42"))
    response = client.get("/me")
    body = response.json()
    assert response.status_code == 500
    assert body["detail"] == SERVER_ERROR
    assert body["request_id"] == response.headers["x-request-id"]
    assert "hunter2" not in response.text and "line 42" not in response.text


def test_busy_database_is_a_503(broken_me):
    broken_me(PoolTimeout("couldn't get a connection"))
    response = client.get("/me")
    assert response.status_code == 503
    assert response.json()["detail"] == BUSY


def test_http_errors_carry_the_request_id():
    response = client.get("/me")  # no token -> 401
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_validation_errors_list_fields_without_echoing_values():
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid.uuid4(), email=None)
    try:
        response = client.put("/onboarding/basics", json={
            "date_of_birth": "2015-01-01", "sex": "male", "height_cm": 1.75,
            "weight_kg": 70, "activity_level": "light",
        })
    finally:
        app.dependency_overrides.clear()
    body = response.json()
    assert response.status_code == 422
    assert body["detail"] == "Please check the highlighted fields."
    fields = {e["field"]: e["message"] for e in body["errors"]}
    assert set(fields) == {"date_of_birth", "height_cm"}
    assert fields["date_of_birth"] == "you must be at least 18 to use this app"  # "Value error, " removed
    assert "1.75" not in response.text and "2015-01-01" not in response.text  # submitted values not echoed


# --- Log lines ---

def test_log_lines_are_json_with_the_request_id():
    token = request_id_var.set("req-abc12345")
    try:
        record = logging.LogRecord("app.request", logging.INFO, __file__, 1, "request", (), None)
        record.status = 200
        line = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert line["msg"] == "request" and line["status"] == 200
    assert line["request_id"] == "req-abc12345" and line["level"] == "INFO"


def test_access_log_has_no_token_or_query_string(caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/me?email=someone@example.com", headers={"Authorization": "Bearer secret-token-xyz"})
    access = [r for r in caplog.records if r.name == "app.request" and r.getMessage() == "request"]
    assert access and access[-1].path == "/me" and access[-1].status == 401
    logged = JsonFormatter().format(access[-1])
    assert "secret-token-xyz" not in logged and "someone@example.com" not in logged
