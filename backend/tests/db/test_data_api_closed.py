import secrets
import uuid

import httpx
import pytest

from app.core.config import get_settings

pytestmark = pytest.mark.db


@pytest.fixture
def signed_in_token():
    """Create a throwaway Auth user, sign in as them, yield their access token, then delete them."""
    s = get_settings()
    base = s.supabase_url.rstrip("/")
    public = {"apikey": s.supabase_publishable_key.get_secret_value()}
    admin = {"apikey": s.supabase_secret_key.get_secret_value()}
    email = f"scratch-{uuid.uuid4()}@example.test"
    password = secrets.token_urlsafe(24)

    created = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=admin,
        json={"email": email, "password": password, "email_confirm": True},
        timeout=15,
    )
    created.raise_for_status()
    user_id = created.json()["id"]
    try:
        login = httpx.post(
            f"{base}/auth/v1/token",
            params={"grant_type": "password"},
            headers=public,
            json={"email": email, "password": password},
            timeout=15,
        )
        login.raise_for_status()
        yield login.json()["access_token"]
    finally:
        httpx.delete(f"{base}/auth/v1/admin/users/{user_id}", headers=admin, timeout=15)


def test_signed_in_user_cannot_reach_tables_through_the_data_api(signed_in_token):
    # D-028: only our backend may reach the tables. A signed-in user calling the Data API
    # directly would skip the backend's checks (18+, nutrition maths, validation).
    s = get_settings()
    response = httpx.get(
        f"{s.supabase_url.rstrip('/')}/rest/v1/profiles",
        params={"select": "id", "limit": 1},
        headers={
            "apikey": s.supabase_publishable_key.get_secret_value(),
            "Authorization": f"Bearer {signed_in_token}",
        },
        timeout=15,
    )
    # Accept only refusals that mean "closed on purpose":
    #  - 503 PGRST002: "Enable Data API" is off. Supabase then points PostgREST at a placeholder
    #    schema (pg_pgrst_no_exposed_schemas) that doesn't exist, so it can never load any table.
    #    Confirmed in the PostgREST logs on 2026-11-05 (error 3F000, schema does not exist).
    #  - 406 PGRST106: Data API on, but `public` removed from the exposed schemas.
    #  - 404: the endpoint is gone entirely.
    # Anything else (200 = open, 401 = token problem, ...) fails.
    code = response.json().get("code") if response.headers.get("content-type", "").startswith("application/json") else None
    closed = (
        (response.status_code == 503 and code == "PGRST002")
        or (response.status_code == 406 and code == "PGRST106")
        or response.status_code == 404
    )
    assert closed, (
        f"Expected the Data API to be closed, got {response.status_code}: {response.text[:200]}. "
        "Supabase dashboard -> Project Settings -> Data API -> turn off 'Enable Data API' and Save."
    )


def test_auth_service_still_works():
    # Turning off the Data API must not affect login/sign-up (a separate service).
    s = get_settings()
    response = httpx.get(
        f"{s.supabase_url.rstrip('/')}/auth/v1/settings",
        headers={"apikey": s.supabase_publishable_key.get_secret_value()},
        timeout=15,
    )
    assert response.status_code == 200
