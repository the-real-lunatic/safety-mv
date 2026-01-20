from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from .artifacts import upload_artifact
from .pipeline import PipelineArtifact


def upload_json_artifact(job_id: UUID, filename: str, payload: dict[str, Any], workdir: Path) -> PipelineArtifact:
    path = workdir / filename
    path.write_text(_json_dumps(payload), encoding="utf-8")
    return upload_artifact(job_id, path)


def _json_dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)
