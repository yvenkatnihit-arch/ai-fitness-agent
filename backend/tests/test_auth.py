"""Token checks with a test key pair made here (no network, no Supabase)."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.core import auth
from app.core.auth import InvalidToken, verify_token
from app.main import app

ISSUER = "https://example.supabase.co/auth/v1"
GOOD_KEY = ec.generate_private_key(ec.SECP256R1())
OTHER_KEY = ec.generate_private_key(ec.SECP256R1())
USER_ID = uuid.uuid4()


@pytest.fixture(autouse=True)
def trust_good_key(monkeypatch):
    """Pretend Supabase's published public key is GOOD_KEY's public half."""
    monkeypatch.setattr(auth, "_issuer", lambda: ISSUER)
    monkeypatch.setattr(auth, "_signing_key", lambda token: GOOD_KEY.public_key())


def make_token(key=GOOD_KEY, algorithm="ES256", **overrides):
    now = int(time.time())
    claims = {
        "sub": str(USER_ID),
        "aud": "authenticated",
        "iss": ISSUER,
        "role": "authenticated",
        "email": "test@example.test",
        "is_anonymous": False,
        "iat": now,
        "exp": now + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}  # None = leave the claim out
    return jwt.encode(claims, key, algorithm=algorithm)


# --- Accepted ---

def test_valid_token_gives_the_user():
    user = verify_token(make_token())
    assert user.id == USER_ID
    assert user.email == "test@example.test"


def test_small_clock_difference_is_tolerated():
    # Issued 10 s "in the future" (server clocks differ slightly): still fine.
    now = int(time.time())
    assert verify_token(make_token(iat=now + 10)).id == USER_ID


# --- Rejected ---

@pytest.mark.parametrize(
    ("description", "overrides"),
    [
        ("expired", {"exp": int(time.time()) - 120}),
        ("wrong audience", {"aud": "someone-else"}),
        ("wrong issuer (another Supabase project)", {"iss": "https://evil.supabase.co/auth/v1"}),
        ("not a signed-in user", {"role": "anon"}),
        ("anonymous session", {"is_anonymous": True}),
        ("sub is not a UUID", {"sub": "admin"}),
        ("no expiry at all", {"exp": None}),
        ("no subject", {"sub": None}),
    ],
)
def test_bad_claims_are_rejected(description, overrides):
    with pytest.raises(InvalidToken):
        verify_token(make_token(**overrides))


def test_token_signed_by_another_key_is_rejected():
    with pytest.raises(InvalidToken):
        verify_token(make_token(key=OTHER_KEY))


def test_tampered_token_is_rejected():
    # Change the payload (e.g. swap in another user's id) without re-signing.
    header, _, signature = make_token().split(".")
    _, forged_payload, _ = make_token(key=OTHER_KEY, sub=str(uuid.uuid4())).split(".")
    with pytest.raises(InvalidToken):
        verify_token(f"{header}.{forged_payload}.{signature}")


def test_unsigned_alg_none_token_is_rejected():
    with pytest.raises(InvalidToken):
        verify_token(make_token(key=None, algorithm="none"))


def test_shared_secret_hs256_token_is_rejected():
    with pytest.raises(InvalidToken):
        verify_token(make_token(key="a-guessed-shared-secret-that-is-long-enough", algorithm="HS256"))


def test_garbage_is_rejected():
    with pytest.raises(InvalidToken):
        verify_token("not.a.jwt")


# --- The /me endpoint's 401 behaviour (no database needed) ---

client = TestClient(app)


def test_me_without_a_token_is_401():
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"detail": "Please sign in."}


def test_me_with_a_bad_token_is_401_with_a_generic_message():
    response = client.get("/me", headers={"Authorization": f"Bearer {make_token(key=OTHER_KEY)}"})
    assert response.status_code == 401
    # The user never learns *why* (signature? expiry?). Details only go to our logs.
    assert response.json() == {"detail": "Your session has expired or is invalid. Please sign in again."}
