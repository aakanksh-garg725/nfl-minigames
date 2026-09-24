from functools import lru_cache
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

bearer = HTTPBearer(auto_error=False)
DEMO_USER = "00000000-0000-4000-8000-000000000001"


@lru_cache
def jwks_client():
    return jwt.PyJWKClient(
        f"{get_settings().supabase_url}/auth/v1/.well-known/jwks.json",
        cache_keys=True,
        lifespan=600,
        timeout=10,
    )


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    settings = get_settings()
    if settings.demo:
        return DEMO_USER
    if not credentials:
        raise HTTPException(401, "Please sign in to continue.")
    token = credentials.credentials
    try:
        algorithm = jwt.get_unverified_header(token).get("alg")
        if algorithm in {"ES256", "RS256"}:
            key = jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
                issuer=f"{settings.supabase_url}/auth/v1",
                options={"require": ["sub", "exp", "aud", "iss"]},
            )
            return str(UUID(payload["sub"]))
        # Older Supabase projects may use HS256. Validate remotely; never decode without verification.
        if algorithm == "HS256" and settings.supabase_publishable_key:
            response = httpx.get(
                f"{settings.supabase_url}/auth/v1/user",
                timeout=10,
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": settings.supabase_publishable_key,
                },
            )
            response.raise_for_status()
            return str(UUID(response.json()["id"]))
    except (jwt.PyJWTError, httpx.HTTPError, ValueError, KeyError):
        pass
    raise HTTPException(401, "Your session has expired. Please sign in again.")


def admin_user(user: str = Depends(current_user)) -> str:
    if user not in get_settings().admin_user_ids.split(","):
        raise HTTPException(403, "Administrator access is required.")
    return user
