from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from ...core.models import JobCreateRequest, JobRecord, JobResponse
from ...core.status import JobStatus, can_transition
from ...core.strategy_loader import list_strategy_ids

router = APIRouter()

_JOBS: dict[UUID, JobRecord] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _supported_strategies() -> list[str]:
    return list_strategy_ids()


@router.get("/strategies")
def list_strategies() -> dict[str, list[str]]:
    return {"strategies": _supported_strategies()}


@router.post("/jobs", response_model=JobResponse)
def create_job(payload: JobCreateRequest) -> JobResponse:
    strategies = _supported_strategies()
    if strategies and payload.strategy not in strategies:
        raise HTTPException(status_code=400, detail="unsupported strategy")

    job_id = uuid4()
    now = _now()
    record = JobRecord(
        job_id=job_id,
        status=JobStatus.queued,
        strategy=payload.strategy,
        created_at=now,
        updated_at=now,
        options=payload.options,
        attachments=payload.attachments,
    )
    _JOBS[job_id] = record
    return JobResponse(**record.model_dump())


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: UUID) -> JobResponse:
    record = _JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobResponse(**record.model_dump())


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job(job_id: UUID) -> JobResponse:
    record = _JOBS.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="job not found")
    if not can_transition(record.status, JobStatus.canceled):
        raise HTTPException(status_code=409, detail="job already finished")
    record.status = JobStatus.canceled
    record.updated_at = _now()
    _JOBS[job_id] = record
    return JobResponse(**record.model_dump())
