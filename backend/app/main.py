from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from minio import Minio
import redis

from .api.routes import jobs_router
from .core.config import settings

app = FastAPI(
    title="SafetyMV Backend",
    version="0.1.0",
    description="Infra-only backend with health checks.",
)

app.include_router(jobs_router)


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


def _http_request(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 5,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _health_response(status: str, detail: str | None = None, http_status: int = 200) -> JSONResponse:
    payload: dict[str, Any] = {"status": status}
    if detail:
        payload["detail"] = detail
    return JSONResponse(payload, status_code=http_status)


def _check_openai_responses(base_url: str, api_key: str, model: str) -> JSONResponse:
    url = f"{base_url.rstrip('/')}/responses"
    payload = json.dumps({"model": model, "input": "healthcheck"}).encode("utf-8")
    status, body = _http_request(
        "POST",
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        body=payload,
    )
    if 200 <= status < 300:
        return _health_response("ok")
    detail = body.decode("utf-8", errors="ignore")[:300]
    return _health_response("down", detail=f"http {status}: {detail}", http_status=503)


def _check_openai_get(base_url: str, api_key: str, path: str) -> JSONResponse:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    status, body = _http_request(
        "GET",
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
    )
    if 200 <= status < 300:
        return _health_response("ok")
    detail = body.decode("utf-8", errors="ignore")[:300]
    return _health_response("down", detail=f"http {status}: {detail}", http_status=503)

def _check_suno_credit(base_url: str, api_key: str) -> JSONResponse:
    url = f"{base_url.rstrip('/')}/api/v1/generate/credit"
    status, body = _http_request(
        "GET",
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
        },
    )
    if 200 <= status < 300:
        try:
            data = json.loads(body.decode("utf-8"))
            if data.get("code") == 200:
                return _health_response("ok")
        except json.JSONDecodeError:
            return _health_response("degraded", detail="invalid json", http_status=503)
    detail = body.decode("utf-8", errors="ignore")[:300]
    return _health_response("down", detail=f"http {status}: {detail}", http_status=503)


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


@app.get("/health/openai")
def health_openai() -> JSONResponse:
    if not settings.openai_api_key:
        return _health_response("missing_key", http_status=503)
    if not settings.openai_healthcheck_model:
        return _health_response("missing_model", http_status=503)
    return _check_openai_responses(
        settings.openai_api_base_url,
        settings.openai_api_key,
        settings.openai_healthcheck_model,
    )


@app.get("/health/sora")
def health_sora() -> JSONResponse:
    if not settings.sora_api_key:
        return _health_response("missing_key", http_status=503)
    return _check_openai_get(settings.sora_api_base_url, settings.sora_api_key, "videos")


@app.get("/health/suno")
def health_suno() -> JSONResponse:
    if not settings.suno_api_key:
        return _health_response("missing_key", http_status=503)
    return _check_suno_credit(settings.suno_api_base_url, settings.suno_api_key)
