from __future__ import annotations

import io
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from .suno_client import SunoClient

router = APIRouter(tags=["suno"])

SUNO_TASK_TTL_SECONDS = 60 * 60 * 6


class SunoGenerateRequest(BaseModel):
    job_id: str | None = None
    lyrics: str = Field(min_length=1)
    style: str = Field(min_length=1)
    title: str = Field(min_length=1)
    custom_mode: bool = Field(default=True)
    instrumental: bool = Field(default=False)
    model: str | None = None
    negative_tags: str | None = None
    vocal_gender: str | None = None
    style_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    weirdness_constraint: float | None = Field(default=None, ge=0.0, le=1.0)
    audio_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    persona_id: str | None = None


def _suno_task_key(task_id: str) -> str:
    return f"safety_mv:suno:task:{task_id}"


def _save_suno_task(task_id: str, payload: dict[str, Any]) -> None:
    from .main import _get_redis_client

    client = _get_redis_client()
    client.set(_suno_task_key(task_id), json.dumps(payload, ensure_ascii=False), ex=SUNO_TASK_TTL_SECONDS)


def _load_suno_task(task_id: str) -> dict[str, Any] | None:
    from .main import _get_redis_client

    client = _get_redis_client()
    raw = client.get(_suno_task_key(task_id))
    if not raw:
        return None
    return json.loads(raw)


def _update_suno_task(task_id: str, **updates: Any) -> dict[str, Any]:
    task = _load_suno_task(task_id) or {"task_id": task_id}
    task.update(updates)
    task["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_suno_task(task_id, task)
    return task


def _validate_suno_payload_limits(request: SunoGenerateRequest, model: str) -> None:
    limits = SunoClient.model_limits(model)
    prompt_limit = limits["prompt"] if request.custom_mode else limits["prompt_non_custom"]
    if len(request.title) > limits["title"]:
        raise HTTPException(status_code=400, detail=f"title too long (max {limits['title']})")
    if len(request.style) > limits["style"]:
        raise HTTPException(status_code=400, detail=f"style too long (max {limits['style']})")
    if len(request.lyrics) > prompt_limit:
        raise HTTPException(status_code=400, detail=f"lyrics too long (max {prompt_limit})")


def _build_suno_payload(request: SunoGenerateRequest, model: str, callback_url: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "customMode": request.custom_mode,
        "instrumental": request.instrumental,
        "model": model,
        "callBackUrl": callback_url,
    }

    if request.custom_mode:
        payload["title"] = request.title
        payload["style"] = request.style
        if not request.instrumental:
            payload["prompt"] = request.lyrics
    else:
        payload["prompt"] = request.lyrics

    if request.negative_tags:
        payload["negativeTags"] = request.negative_tags
    if request.vocal_gender:
        payload["vocalGender"] = request.vocal_gender
    if request.style_weight is not None:
        payload["styleWeight"] = request.style_weight
    if request.weirdness_constraint is not None:
        payload["weirdnessConstraint"] = request.weirdness_constraint
    if request.audio_weight is not None:
        payload["audioWeight"] = request.audio_weight
    if request.persona_id:
        payload["personaId"] = request.persona_id

    return payload


@router.post("/suno/generate")
def suno_generate(payload: SunoGenerateRequest) -> dict[str, Any]:
    if payload.job_id:
        from .main import _load_job

        job = _load_job(payload.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")

    client = SunoClient()
    model = payload.model or client.default_model
    _validate_suno_payload_limits(payload, model)
    request_body = _build_suno_payload(payload, model, client.callback_url)

    try:
        response = client.generate_music(request_body)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"suno api error: {exc}") from exc

    data = response.get("data") or {}
    task_id = data.get("task_id") or data.get("taskId")
    if not task_id:
        raise HTTPException(status_code=502, detail="suno api response missing task_id")

    _update_suno_task(
        task_id,
        status="queued",
        job_id=payload.job_id,
        request=request_body,
        response=response,
    )
    if payload.job_id:
        from .main import _update_job

        _update_job(payload.job_id, suno={"task_id": task_id, "status": "queued"})

    return {"task_id": task_id}


@router.get("/suno/tasks/{task_id}")
def get_suno_task(task_id: str) -> dict[str, Any]:
    task = _load_suno_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


def _download_bytes(url: str, timeout_seconds: float = 60.0) -> tuple[bytes, str | None]:
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.content, response.headers.get("content-type")


def _store_suno_assets(task_id: str, items: list[dict[str, Any]], job_id: str | None) -> list[dict[str, Any]]:
    from .main import _get_minio_client

    minio_client = _get_minio_client()
    bucket_name = os.getenv("MINIO_BUCKET_MUSIC", "safety-mv")
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    stored: list[dict[str, Any]] = []
    job_prefix = job_id or "unknown"
    for item in items:
        track_id = item.get("id") or uuid4().hex
        audio_url = item.get("audio_url")
        image_url = item.get("image_url")

        audio_key = None
        if audio_url:
            audio_bytes, audio_type = _download_bytes(audio_url)
            audio_key = f"suno/{job_prefix}/{task_id}/{track_id}.mp3"
            minio_client.put_object(
                bucket_name,
                audio_key,
                io.BytesIO(audio_bytes),
                length=len(audio_bytes),
                content_type=audio_type or "audio/mpeg",
            )

        image_key = None
        if image_url:
            image_bytes, image_type = _download_bytes(image_url)
            image_key = f"suno/{job_prefix}/{task_id}/{track_id}.jpg"
            minio_client.put_object(
                bucket_name,
                image_key,
                io.BytesIO(image_bytes),
                length=len(image_bytes),
                content_type=image_type or "image/jpeg",
            )

        stored.append(
            {
                **item,
                "minio_audio_key": audio_key,
                "minio_image_key": image_key,
                "minio_bucket": bucket_name,
            }
        )
    return stored


@router.post("/callbacks/suno/music")
def suno_callback(payload: dict[str, Any], background_tasks: BackgroundTasks) -> dict[str, Any]:
    data = payload.get("data") or {}
    task_id = data.get("task_id")
    callback_type = data.get("callbackType")
    if not task_id:
        return {"ok": True}

    task = _update_suno_task(task_id, last_callback=payload, status=callback_type or "unknown")
    job_id = task.get("job_id")
    if job_id:
        from .main import _update_job

        _update_job(job_id, suno={"task_id": task_id, "status": callback_type, "last_callback": payload})

    if callback_type == "complete":
        items = data.get("data") or []
        if items:
            background_tasks.add_task(_handle_suno_complete, task_id, items, job_id)

    return {"ok": True}


def _handle_suno_complete(task_id: str, items: list[dict[str, Any]], job_id: str | None) -> None:
    try:
        stored_tracks = _store_suno_assets(task_id, items, job_id)
    except Exception as exc:  # noqa: BLE001
        task = _update_suno_task(task_id, status="store_failed", error=str(exc))
        if job_id:
            from .main import _update_job

            _update_job(job_id, suno={"task_id": task_id, "status": task.get("status"), "error": str(exc)})
        return

    task = _update_suno_task(task_id, status="stored", tracks=stored_tracks)
    if job_id:
        from .main import _update_job

        _update_job(job_id, suno={"task_id": task_id, "status": task.get("status"), "tracks": stored_tracks})
