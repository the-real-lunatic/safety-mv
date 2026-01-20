from __future__ import annotations

from typing import Any

from ..core.pipeline import PipelineArtifact, PipelineContext
from ..core.pipeline_helpers import upload_json_artifact


def save_json(context: PipelineContext, filename: str, payload: dict[str, Any]) -> PipelineArtifact:
    workdir = context.ensure_workdir()
    return upload_json_artifact(context.job_id, filename, payload, workdir)
