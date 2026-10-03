from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.firebase_auth import verify_firebase_token
from app.database import get_db

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> dict:
    """
    FastAPI dependency that validates the Firebase Bearer token.

    Extracts the token from the ``Authorization: Bearer <token>`` header,
    verifies it with Firebase Admin SDK, and returns the decoded claims dict.

    Raises:
        HTTPException 401: If the token is missing, expired, or invalid.
    """
    token = credentials.credentials

    # Allow fast local development testing when in development mode
    from app.config import settings
    if settings.APP_ENV == "development" and (token.startswith("dev-") or token in ("dev-token", "mock-token")):
        uid = "dev-user" if token in ("dev-token", "mock-token", "dev-user") else token[4:]
        return {"uid": uid, "email": f"{uid}@moontales.local"}

    try:
        decoded = await verify_firebase_token(token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired Firebase token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return decoded


# Convenience type alias for annotated dependency injection
CurrentUser = Annotated[dict, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
