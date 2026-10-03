"""
Storage Service — Google Cloud Storage.

Uploads story assets (images, audio) and returns signed URLs valid for 1 hour.
"""

import asyncio
import logging
from datetime import timedelta

from google.cloud import storage

from app.config import settings

logger = logging.getLogger(__name__)

import json
from google.oauth2 import service_account

# Module-level GCS client (thread-safe, reused across requests)
_gcs_client: storage.Client | None = None


def _get_client() -> storage.Client:
    """Return a cached GCS client, creating it on first call."""
    global _gcs_client
    if _gcs_client is None:
        if settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip():
            try:
                info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
                creds = service_account.Credentials.from_service_account_info(info)
                _gcs_client = storage.Client(
                    project=settings.GCS_PROJECT_ID,
                    credentials=creds,
                )
                return _gcs_client
            except Exception as exc:
                logger.warning(
                    "Could not load service account from FIREBASE_SERVICE_ACCOUNT_JSON for GCS: %s",
                    exc,
                )
        _gcs_client = storage.Client(project=settings.GCS_PROJECT_ID)
    return _gcs_client


async def upload_file(
    data: bytes,
    destination_path: str,
    content_type: str,
) -> str:
    """
    Upload raw bytes to GCS and return the ``gs://`` URI.

    The upload runs in a thread pool executor so it does not block the event loop.

    Args:
        data: Raw file bytes to upload.
        destination_path: GCS object path, e.g.
            ``stories/{story_id}/page_1/image.png``.
        content_type: MIME type, e.g. ``"image/png"`` or ``"audio/mpeg"``.

    Returns:
        The canonical GCS URI: ``gs://{bucket}/{destination_path}``.
    """
    def _upload() -> str:
        client = _get_client()
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(destination_path)
        blob.upload_from_string(data, content_type=content_type)
        gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{destination_path}"
        logger.info("Uploaded %d bytes → %s", len(data), gcs_uri)
        return gcs_uri

    return await asyncio.to_thread(_upload)


def get_signed_url(gcs_uri: str, expiry_hours: int = 1) -> str:
    """
    Generate a v4 signed URL for a GCS object.

    Args:
        gcs_uri: The ``gs://bucket/path`` URI of the object.
        expiry_hours: How long the signed URL should remain valid.

    Returns:
        An HTTPS signed URL that allows unauthenticated GET access for
        ``expiry_hours`` hours.

    Raises:
        ValueError: If the URI format is unexpected.
    """
    if not gcs_uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI, got: {gcs_uri!r}")

    # Strip the scheme and split off the bucket name
    without_scheme = gcs_uri[len("gs://"):]
    bucket_name, _, object_path = without_scheme.partition("/")

    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_path)

    signed_url: str = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(hours=expiry_hours),
        method="GET",
    )

    logger.info(
        "Generated signed URL for %s (expires in %dh).", gcs_uri, expiry_hours
    )
    return signed_url
