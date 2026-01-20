from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from .status import JobStatus


class JobOptions(BaseModel):
    duration_seconds: int = Field(60, ge=30, le=90)
    mood: str | None = None
    site_type: str | None = None


class JobAttachments(BaseModel):
    reference_images: list[str] = Field(default_factory=list)
    reference_videos: list[str] = Field(default_factory=list)
    reference_audio: list[str] = Field(default_factory=list)


class JobCreateRequest(BaseModel):
    safety_text: str = Field(..., min_length=1)
    strategy: str = Field("parallel_stylelock")
    options: JobOptions = Field(default_factory=JobOptions)
    attachments: JobAttachments | None = None


class JobArtifact(BaseModel):
    kind: str
    uri: str
    meta: dict[str, Any] = Field(default_factory=dict)


class JobRecord(BaseModel):
    job_id: UUID
    status: JobStatus
    strategy: str
    safety_text: str
    created_at: datetime
    updated_at: datetime
    options: JobOptions
    attachments: JobAttachments | None = None
    artifacts: list[JobArtifact] = Field(default_factory=list)
    error: str | None = None


class JobResponse(BaseModel):
    job_id: UUID
    status: JobStatus
    strategy: str
    safety_text: str | None = None
    created_at: datetime
    updated_at: datetime
    options: JobOptions | None = None
    attachments: JobAttachments | None = None
    artifacts: list[JobArtifact]
    error: str | None = None
