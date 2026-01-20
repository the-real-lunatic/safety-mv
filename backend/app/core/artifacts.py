from __future__ import annotations

from pathlib import Path
from uuid import UUID

from .config import settings
from .minio_storage import upload_file
from .pipeline import PipelineArtifact
from .storage import job_dir


def upload_artifact(job_id: UUID, path: Path) -> PipelineArtifact:
    if settings.pipeline_mode == "mock" or not settings.minio_enabled:
        root = job_dir(job_id)
        local_path = root / path.name
        if local_path != path:
            local_path.write_bytes(path.read_bytes())
        return PipelineArtifact(kind="file", uri=f"file://{local_path}", meta={"filename": path.name})

    object_name = f"{job_id}/{path.name}"
    info = upload_file(settings.minio_bucket, object_name, path)
    return PipelineArtifact(
        kind="minio",
        uri=info["url"],
        meta={"bucket": info["bucket"], "object": info["object"], "filename": path.name},
    )
