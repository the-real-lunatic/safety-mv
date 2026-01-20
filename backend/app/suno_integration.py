from __future__ import annotations

from datetime import timedelta
import os
from urllib.parse import urlparse, urlunparse

from .suno_routes import SunoGenerateRequest, suno_generate


def trigger_suno_for_job(job_id: str, result: dict | None = None) -> None:
    from .main import _load_job, _update_job

    job = _load_job(job_id)
    if not job:
        return

    suno_state = (job.get("suno") or {}).get("status")
    if suno_state in {"queued", "complete", "stored"}:
        return

    result = result or job.get("result") or {}
    artifacts = (result.get("job") or {}).get("artifacts") or {}
    selected = artifacts.get("selected_concept") or {}
    lyrics = selected.get("lyrics") or ""
    if not lyrics:
        _update_job(job_id, suno={"status": "error", "error": "missing lyrics"})
        return

    config = artifacts.get("config") or (job.get("payload") or {}).get("config") or {}
    genre = config.get("genre") or "hiphop"
    mood = config.get("mood") or "default"
    style = f"{genre} / {mood}".strip()
    title = f"Safety MV {job_id}"

    try:
        suno_generate(
            SunoGenerateRequest(
                job_id=job_id,
                lyrics=lyrics,
                style=style,
                title=title,
            )
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, suno={"status": "error", "error": str(exc)})


def _rewrite_public_url(url: str) -> str:
    public_endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT")
    if not public_endpoint:
        return url

    parsed = urlparse(url)
    public_parsed = urlparse(
        public_endpoint if "://" in public_endpoint else f"http://{public_endpoint}"
    )
    scheme = public_parsed.scheme or parsed.scheme
    netloc = public_parsed.netloc
    return urlunparse((scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


def _presign_minio_object(bucket: str, key: str) -> str | None:
    from .main import _get_minio_client

    if not bucket or not key:
        return None
    client = _get_minio_client()
    try:
        url = client.presigned_get_object(bucket, key, expires=timedelta(hours=1))
    except Exception:
        return None
    return _rewrite_public_url(url)


def attach_public_suno(job: dict) -> dict:
    suno = job.get("suno")
    if not suno:
        return job
    tracks = suno.get("tracks") or []
    if not tracks:
        return job

    public_tracks = []
    default_bucket = os.getenv("MINIO_BUCKET_MUSIC", "safety-mv")
    for track in tracks:
        bucket = track.get("minio_bucket") or default_bucket
        public_tracks.append(
            {
                **track,
                "minio_audio_url": _presign_minio_object(bucket, track.get("minio_audio_key")),
                "minio_image_url": _presign_minio_object(bucket, track.get("minio_image_key")),
            }
        )

    suno["public_tracks"] = public_tracks
    return job
