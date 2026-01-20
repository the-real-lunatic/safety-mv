from __future__ import annotations

import os
from pathlib import Path

from .config import settings


def _resolve_strategy_dir() -> Path:
    env_path = settings.strategy_dir
    if env_path:
        return Path(env_path)
    return Path("strategies")


def list_strategy_ids() -> list[str]:
    root = _resolve_strategy_dir()
    if not root.exists():
        return []
    if root.is_file():
        return []
    strategy_ids: list[str] = []
    for item in sorted(root.iterdir()):
        if item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.suffix.lower() != ".md":
            continue
        if item.stem.lower() == "readme":
            continue
        strategy_ids.append(item.stem)
    return strategy_ids
