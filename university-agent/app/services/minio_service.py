"""MinIO (S3-compatible) client for file storage."""

from __future__ import annotations

import asyncio
import io
import logging
from concurrent.futures import ThreadPoolExecutor

from minio import Minio

from app.config import settings

logger = logging.getLogger(__name__)

_client: Minio | None = None
_presign_client: Minio | None = None
_minio_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="minio")


def get_minio() -> Minio:
    """Return a shared MinIO client (lazy-initialized) — internal endpoint, for upload/download."""
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def _get_presign_client() -> Minio:
    """Return a MinIO client configured with the *public* endpoint.

    Presigned URLs encode the endpoint host into the SigV4 signature, so the
    URL must be signed with whatever host the end user (Telegram client,
    browser) will actually hit. If MINIO_PUBLIC_ENDPOINT is unset, falls back
    to the internal endpoint (useful for local dev with host networking).

    We pin region="us-east-1" so minio-py doesn't try a live GetBucketLocation
    against the public endpoint (which is usually unreachable from inside
    the agent container).
    """
    global _presign_client
    if _presign_client is None:
        if settings.minio_public_endpoint:
            endpoint = settings.minio_public_endpoint
            secure = settings.minio_public_secure
        else:
            endpoint = settings.minio_endpoint
            secure = settings.minio_secure
        _presign_client = Minio(
            endpoint=endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=secure,
            region="us-east-1",
        )
    return _presign_client


def ensure_bucket() -> None:
    """Create the default bucket if it doesn't exist."""
    client = get_minio()
    bucket = settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket: %s", bucket)


# ── Upload / Download ────────────────────────────────────────────────────────


def upload_bytes(
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Upload raw bytes and return the object name."""
    client = get_minio()
    bucket = bucket or settings.minio_bucket
    client.put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def download_bytes(object_name: str, bucket: str | None = None) -> bytes:
    """Download an object and return raw bytes."""
    client = get_minio()
    bucket = bucket or settings.minio_bucket
    response = client.get_object(bucket_name=bucket, object_name=object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def presigned_url(
    object_name: str,
    bucket: str | None = None,
    expires_hours: int = 24,
) -> str:
    """Generate a presigned download URL using the public endpoint."""
    from datetime import timedelta

    client = _get_presign_client()
    bucket = bucket or settings.minio_bucket
    return client.presigned_get_object(
        bucket_name=bucket,
        object_name=object_name,
        expires=timedelta(hours=expires_hours),
    )


# ── Async wrappers ──────────────────────────────────────────────────────────


async def upload_bytes_async(
    object_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Non-blocking upload via thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _minio_executor,
        lambda: upload_bytes(object_name, data, content_type, bucket),
    )


async def download_bytes_async(object_name: str, bucket: str | None = None) -> bytes:
    """Non-blocking download via thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _minio_executor,
        lambda: download_bytes(object_name, bucket),
    )


async def presigned_url_async(
    object_name: str,
    bucket: str | None = None,
    expires_hours: int = 24,
) -> str:
    """Non-blocking presigned URL generation via thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _minio_executor,
        lambda: presigned_url(object_name, bucket, expires_hours),
    )


# ── Health check ─────────────────────────────────────────────────────────────


def ping() -> bool:
    try:
        client = get_minio()
        client.list_buckets()
        return True
    except Exception:
        logger.exception("MinIO ping failed")
        return False
