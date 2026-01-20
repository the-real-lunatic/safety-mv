from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from .config import settings


def minio_client():
    from minio import Minio

    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def ensure_bucket(bucket: str) -> None:
    client = minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_file(bucket: str, object_name: str, path: Path) -> dict[str, Any]:
    client = minio_client()
    client.fput_object(bucket, object_name, str(path))
    url = client.presigned_get_object(bucket, object_name, expires=timedelta(hours=6))
    return {"bucket": bucket, "object": object_name, "url": url}
