"""Verify Supabase login tokens (JWTs) on every protected request.

Supabase signs tokens with ES256 (a private key only Supabase holds) and publishes the
matching public keys at /auth/v1/.well-known/jwks.json. We check each token with those
public keys, so the backend needs no secret for this.

Checked: signature, expiry, audience ("authenticated"), issuer (our project), sub is a UUID,
role is "authenticated", and the session isn't anonymous.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Asymmetric algorithms only. Never HS256 (shared secret) and never "none" (unsigned).
ALGORITHMS = ["ES256", "RS256"]
AUDIENCE = "authenticated"
CLOCK_SKEW_S = 30  # tolerate small clock differences between Supabase and our server
JWKS_CACHE_S = 3600


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None


class InvalidToken(Exception):
    """The token can't be trusted. The message is for logs only, never for the user."""


_jwks_client: jwt.PyJWKClient | None = None


def _issuer() -> str:
    return f"{get_settings().supabase_url.rstrip('/')}/auth/v1"


def _signing_key(token: str):
    """Public key for this token, from Supabase's JWKS (cached for an hour)."""
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = jwt.PyJWKClient(
            f"{_issuer()}/.well-known/jwks.json", cache_keys=True, lifespan=JWKS_CACHE_S, timeout=10
        )
    return _jwks_client.get_signing_key_from_jwt(token).key


def verify_token(token: str) -> CurrentUser:
    """Return the user a token belongs to, or raise InvalidToken."""
    try:
        claims = jwt.decode(
            token,
            _signing_key(token),
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=_issuer(),
            leeway=CLOCK_SKEW_S,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except jwt.PyJWTError as error:  # bad signature, expired, wrong audience, unknown key, ...
        raise InvalidToken(f"{type(error).__name__}: {error}") from error

    if claims.get("role") != "authenticated":
        raise InvalidToken(f"role is {claims.get('role')!r}")
    if claims.get("is_anonymous"):
        raise InvalidToken("anonymous session")
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError as error:
        raise InvalidToken("sub is not a UUID") from error

    return CurrentUser(id=user_id, email=claims.get("email"))


_bearer = HTTPBearer(auto_error=False)

_NOT_SIGNED_IN = "Please sign in."
_BAD_SESSION = "Your session has expired or is invalid. Please sign in again."


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    """FastAPI dependency: the verified user, or 401. Use it on every protected endpoint."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _NOT_SIGNED_IN, headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_token(credentials.credentials)
    except InvalidToken as error:
        logger.info("rejected token: %s", error)  # details for us; the user gets a generic message
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, _BAD_SESSION, headers={"WWW-Authenticate": "Bearer"}
        ) from None
