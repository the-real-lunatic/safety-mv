from __future__ import annotations

import threading
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ...core.models import JobCreateRequest, JobRecord, JobResponse, JobArtifact
from ...core.pipeline import PipelineContext
from ...core.storage import job_dir
from ...core.uploads import store_upload
from ...core.pdf_reader import read_pdf_texts
from ...core.status import JobStatus, can_transition
from ...core.strategy_loader import list_strategy_ids
from ...strategies import get_strategy

router = APIRouter()

_JOBS: dict[UUID, JobRecord] = {}
_LOCK = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _supported_strategies() -> list[str]:
    return list_strategy_ids()


@router.get("/strategies")
def list_strategies() -> dict[str, list[str]]:
    return {"strategies": _supported_strategies()}


@router.post("/jobs", response_model=JobResponse)
def create_job(payload: JobCreateRequest, background: BackgroundTasks) -> JobResponse:
    strategies = _supported_strategies()
    if strategies and payload.strategy not in strategies:
        raise HTTPException(status_code=400, detail="unsupported strategy")

    job_id = uuid4()
    now = _now()
    record = JobRecord(
        job_id=job_id,
        status=JobStatus.queued,
        strategy=payload.strategy,
        prompt=payload.prompt,
        pdf_paths=payload.pdf_paths,
        created_at=now,
        updated_at=now,
        options=payload.options,
        attachments=payload.attachments,
    )
    with _LOCK:
        _JOBS[job_id] = record

    background.add_task(_execute_job, job_id)
    return JobResponse(**record.model_dump())


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> JobResponse:
    record = _JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(**record.model_dump())


@router.get("/jobs/{job_id}/artifacts/{filename}")
def download_artifact(job_id: UUID, filename: str) -> FileResponse:
    root = job_dir(job_id)
    path = (root / filename).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact not found")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="artifact not found")
    if not path.is_relative_to(root.resolve()):
        raise HTTPException(status_code=400, detail="invalid path")
    return FileResponse(path)


@router.post("/uploads")
async def upload_pdfs(files: list[UploadFile] = File(...)) -> dict[str, list[str]]:
    saved: list[str] = []
    for upload in files:
        target = store_upload(upload.filename)
        content = await upload.read()
        target.write_bytes(content)
        saved.append(str(target))
    return {"pdf_paths": saved}


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: UUID) -> JobResponse:
    record = _JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not can_transition(record.status, JobStatus.canceled):
        raise HTTPException(status_code=409, detail="job already finished")
    record.status = JobStatus.canceled
    record.updated_at = _now()
    with _LOCK:
        _JOBS[job_id] = record
    return JobResponse(**record.model_dump())


@router.post("/jobs/{job_id}/run", response_model=JobResponse)
def run_job(job_id: UUID, background: BackgroundTasks) -> JobResponse:
    record = _JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    if record.status != JobStatus.queued:
        raise HTTPException(status_code=409, detail="job not queued")
    background.add_task(_execute_job, job_id)
    return JobResponse(**record.model_dump())


def _execute_job(job_id: UUID) -> None:
    with _LOCK:
        record = _JOBS.get(job_id)
        if record is None:
            return
        if record.status != JobStatus.queued:
            return
        record.status = JobStatus.running
        record.updated_at = _now()
        _JOBS[job_id] = record

    try:
        strategy = get_strategy(record.strategy)
        pdf_texts = read_pdf_texts(record.pdf_paths)
        context = PipelineContext(
            job_id=record.job_id,
            strategy_id=record.strategy,
            prompt=record.prompt,
            pdf_paths=record.pdf_paths,
            pdf_texts=pdf_texts,
            options=record.options.model_dump(),
            attachments=record.attachments.model_dump() if record.attachments else None,
        )
        result = strategy.run(context)
        record.artifacts = [
            JobArtifact(kind=artifact.kind, uri=artifact.uri, meta=artifact.meta)
            for artifact in result.artifacts
        ]
        record.status = JobStatus.completed
        record.updated_at = _now()
    except Exception as exc:  # noqa: BLE001
        record.status = JobStatus.failed
        record.error = str(exc)
        record.updated_at = _now()

    with _LOCK:
        _JOBS[job_id] = record
