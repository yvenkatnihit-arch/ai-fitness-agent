from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_never_touches_the_database(monkeypatch):
    def fail():
        raise AssertionError("/health must not call the database")

    monkeypatch.setattr(db, "ping", fail)
    assert client.get("/health").status_code == 200


def test_ready_when_database_answers(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: True)
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_ready_returns_503_when_database_is_down(monkeypatch):
    monkeypatch.setattr(db, "ping", lambda: False)
    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
