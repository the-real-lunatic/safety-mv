from __future__ import annotations

from pathlib import Path
from uuid import UUID


ARTIFACT_ROOT = Path("/tmp/safetymv")


def job_dir(job_id: UUID) -> Path:
    return ARTIFACT_ROOT / str(job_id)


def artifact_path(job_id: UUID, filename: str) -> Path:
    return job_dir(job_id) / filename
