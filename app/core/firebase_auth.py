import json
import logging

import firebase_admin
from firebase_admin import auth, credentials

from app.config import settings

logger = logging.getLogger(__name__)

_firebase_initialized = False


def initialize_firebase() -> None:
    """
    Initialize the Firebase Admin SDK exactly once at application startup.

    Priority:
    1. FIREBASE_SERVICE_ACCOUNT_JSON env var (JSON string)
    2. GOOGLE_APPLICATION_CREDENTIALS env var (file path) — handled automatically
       by the Firebase SDK when no explicit credential is provided.
    """
    global _firebase_initialized

    if _firebase_initialized:
        return

    if firebase_admin._apps:
        _firebase_initialized = True
        return

    if settings.FIREBASE_SERVICE_ACCOUNT_JSON:
        try:
            service_account_info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
            cred = credentials.Certificate(service_account_info)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized from FIREBASE_SERVICE_ACCOUNT_JSON.")
        except (json.JSONDecodeError, ValueError) as exc:
            logger.error("Failed to parse FIREBASE_SERVICE_ACCOUNT_JSON: %s", exc)
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is set but contains invalid JSON."
            ) from exc
    else:
        # Fall back to Application Default Credentials / GOOGLE_APPLICATION_CREDENTIALS
        firebase_admin.initialize_app()
        logger.info(
            "Firebase Admin SDK initialized from Application Default Credentials."
        )

    _firebase_initialized = True


async def verify_firebase_token(token: str) -> dict:
    """
    Verify a Firebase ID token and return the decoded claims.

    Args:
        token: The raw Bearer token string from the Authorization header.

    Returns:
        Decoded token dict containing at minimum ``uid`` and ``email``.

    Raises:
        firebase_admin.auth.InvalidIdTokenError: If the token is invalid or expired.
    """
    # firebase_admin.auth.verify_id_token is synchronous; run it directly —
    # it completes in < 1 ms for cached public keys (network call only on first
    # request or key rotation).
    decoded: dict = auth.verify_id_token(token)
    return decoded
