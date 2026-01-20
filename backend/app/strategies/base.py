from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..core.pipeline import PipelineContext, PipelineResult


@dataclass(slots=True)
class Strategy:
    strategy_id: str

    def run(self, context: PipelineContext) -> PipelineResult:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass(slots=True)
class StrategyOutput:
    data: dict[str, Any]
    artifacts: list[dict[str, Any]]
