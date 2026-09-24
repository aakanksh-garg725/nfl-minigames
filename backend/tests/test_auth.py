from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth
from app.core.config import Settings


@pytest.fixture
def signing(monkeypatch):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    settings = Settings(
        _env_file=None, auth_mode="supabase", supabase_url="https://example.supabase.co"
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth,
        "jwks_client",
        lambda: SimpleNamespace(
            get_signing_key_from_jwt=lambda token: SimpleNamespace(key=key.public_key())
        ),
    )
    return key


def make_token(signing, **overrides):
    claims = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "iss": "https://example.supabase.co/auth/v1",
        "exp": datetime.now(UTC) + timedelta(minutes=10),
    }
    claims.update(overrides)
    return HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=jwt.encode(claims, signing, algorithm="RS256")
    ), claims


def test_verified_identity(signing):
    token, claims = make_token(signing)
    assert auth.current_user(token) == claims["sub"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "anon"},
        {"iss": "https://wrong-project.supabase.co/auth/v1"},
        {"exp": datetime.now(UTC) - timedelta(seconds=1)},
        {"sub": "not-a-uuid"},
    ],
)
def test_reject_invalid_claims(signing, overrides):
    token, _ = make_token(signing, **overrides)
    with pytest.raises(HTTPException) as error:
        auth.current_user(token)
    assert error.value.status_code == 401


def test_signature_tampering_rejected(signing):
    unrelated = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token, _ = make_token(unrelated)
    with pytest.raises(HTTPException):
        auth.current_user(token)


def test_demo_cannot_run_on_remote_database():
    settings = Settings(_env_file=None, auth_mode="demo", database_url="postgresql://example")
    with pytest.raises(ValueError):
        settings.validate_runtime()
