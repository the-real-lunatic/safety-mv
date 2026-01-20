from __future__ import annotations

from pathlib import Path
from uuid import uuid4

UPLOAD_ROOT = Path("/tmp/safetymv/uploads")


def ensure_upload_dir() -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return UPLOAD_ROOT


def store_upload(filename: str) -> Path:
    safe_name = f"{uuid4().hex}_{Path(filename).name}"
    return ensure_upload_dir() / safe_name
