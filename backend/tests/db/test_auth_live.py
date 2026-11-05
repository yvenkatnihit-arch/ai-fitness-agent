"""End to end: a real Supabase login token -> our /me endpoint -> a query under RLS."""

import secrets
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import admin_transaction, close_pool
from app.main import app

pytestmark = pytest.mark.db


@pytest.fixture
def real_user():
    """A throwaway Supabase Auth user. Yields (user_id, access_token, email); deleted afterwards."""
    s = get_settings()
    base = s.supabase_url.rstrip("/")
    admin = {"apikey": s.supabase_secret_key.get_secret_value()}
    email, password = f"scratch-{uuid.uuid4()}@example.test", secrets.token_urlsafe(24)
    created = httpx.post(f"{base}/auth/v1/admin/users", headers=admin,
                         json={"email": email, "password": password, "email_confirm": True}, timeout=15)
    created.raise_for_status()
    user_id = uuid.UUID(created.json()["id"])
    try:
        login = httpx.post(f"{base}/auth/v1/token", params={"grant_type": "password"},
                           headers={"apikey": s.supabase_publishable_key.get_secret_value()},
                           json={"email": email, "password": password}, timeout=15)
        login.raise_for_status()
        yield user_id, login.json()["access_token"], email
    finally:
        httpx.delete(f"{base}/auth/v1/admin/users/{user_id}", headers=admin, timeout=15)  # cascades


@pytest.fixture
def client():
    with TestClient(app) as c:  # runs shutdown, which closes the pool
        yield c
    close_pool()


def test_me_with_a_real_supabase_token(client, real_user):
    user_id, token, email = real_user
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"id": str(user_id), "email": email, "has_profile": False}


def test_me_sees_the_profile_once_it_exists(client, real_user):
    user_id, token, _ = real_user
    with admin_transaction("test setup: create profile") as conn:
        conn.execute("insert into public.profiles (id) values (%s)", (user_id,))
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.json()["has_profile"] is True


def test_real_token_with_one_character_changed_is_rejected(client, real_user):
    _, token, _ = real_user
    header, payload, signature = token.split(".")
    flipped = signature[:-2] + ("A" if signature[-2] != "A" else "B") + signature[-1]
    response = client.get("/me", headers={"Authorization": f"Bearer {header}.{payload}.{flipped}"})
    assert response.status_code == 401
