from __future__ import annotations

from typing import Any

from .pipeline import PipelineContext
from ..strategies.common_steps import Providers


def generate_lyrics(context: PipelineContext, providers: Providers) -> dict[str, Any]:
    if providers.openai is None:
        return {
            "hooks": ["안전은 습관", "사고는 순간"],
            "verses": [context.prompt],
        }

    prompt = (
        "역할: 안전 MV 가사 생성기\n"
        "목표: 안전 규칙을 짧은 훅 + 벌스로 구성\n"
        "출력: hooks[] + verses[]\n\n"
        f"context:\n{context.combined_text()}\n"
    )
    response = providers.openai.responses(prompt)
    if isinstance(response, dict):
        hooks = response.get("hooks")
        verses = response.get("verses")
        if isinstance(hooks, list) and isinstance(verses, list):
            return {"hooks": hooks, "verses": verses}
    return {"hooks": ["안전은 습관"], "verses": [context.prompt]}


def lyrics_prompt(lyrics: dict[str, Any]) -> str:
    hooks = " / ".join(str(item) for item in lyrics.get("hooks", []))
    verses = " / ".join(str(item) for item in lyrics.get("verses", []))
    return f"Hooks: {hooks}. Verses: {verses}."
