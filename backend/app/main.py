from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from minio import Minio
import redis

app = FastAPI(
    title="SafetyMV Backend",
    version="0.1.0",
    description="Infra-only backend with health checks.",
)


def _get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _get_minio_client() -> Minio:
    return Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/health/redis")
def health_redis() -> JSONResponse:
    try:
        client = _get_redis_client()
        pong = client.ping()
        if pong is True:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "degraded", "detail": "ping failed"}, status_code=503)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "down", "detail": str(exc)}, status_code=503)


@app.get("/health/minio")
def health_minio() -> JSONResponse:
    try:
        client = _get_minio_client()
        # A lightweight call to verify connectivity/auth
        list(client.list_buckets())
        return JSONResponse({"status": "ok"})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "down", "detail": str(exc)}, status_code=503)
