from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from .storage import ensure_job_dir


@dataclass(slots=True)
class PipelineArtifact:
    kind: str
    uri: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineResult:
    artifacts: list[PipelineArtifact]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineContext:
    job_id: UUID
    strategy_id: str
    safety_text: str
    options: dict[str, Any]
    attachments: dict[str, Any] | None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def ensure_workdir(self) -> Path:
        return ensure_job_dir(self.job_id)

    def write_json(self, filename: str, payload: dict[str, Any]) -> PipelineArtifact:
        workdir = self.ensure_workdir()
        path = workdir / filename
        path.write_text(_json_dumps(payload), encoding="utf-8")
        return PipelineArtifact(kind="json", uri=f"file://{path}", meta={"filename": filename})


class PipelineError(RuntimeError):
    pass


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


PipelineStep = Callable[[PipelineContext, dict[str, Any]], dict[str, Any]]
