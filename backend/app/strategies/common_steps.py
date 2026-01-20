from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from ..core.clients import OpenAIClient, SoraClient, SunoClient
from ..core.config import settings
from ..core.pipeline import PipelineContext, PipelineError


@dataclass(slots=True)
class Providers:
    openai: OpenAIClient | None
    sora: SoraClient | None
    suno: SunoClient | None


def build_providers(mode: str) -> Providers:
    if mode == "mock":
        return Providers(openai=None, sora=None, suno=None)

    if not settings.openai_api_key or not settings.openai_text_model:
        raise PipelineError("OPENAI_API_KEY and OPENAI_TEXT_MODEL required for real mode")
    if settings.sora_enabled and (not settings.sora_api_key or not settings.sora_model):
        raise PipelineError("SORA_API_KEY and SORA_MODEL required for real mode")
    if not settings.suno_api_key:
        raise PipelineError("SUNO_API_KEY required for real mode")

    return Providers(
        openai=OpenAIClient(settings.openai_api_base_url, settings.openai_api_key, settings.openai_text_model),
        sora=(
            SoraClient(settings.sora_api_base_url, settings.sora_api_key, settings.sora_model)
            if settings.sora_enabled
            else None
        ),
        suno=SunoClient(settings.suno_api_base_url, settings.suno_api_key, settings.suno_model),
    )


def parse_sentences(context: PipelineContext, providers: Providers) -> list[str]:
    source_text = context.combined_text()
    if providers.openai is None:
        text = source_text.replace("\n", " ")
        return [part.strip() for part in text.split(".") if part.strip()]
    prompt = (
        "역할: 안전문서 파서\n"
        "목표: 입력 텍스트를 문장 배열로 분해\n"
        "출력: sentences[] (원문 유지)\n\n"
        f"safety_text:\n{source_text}\n"
    )
    response = providers.openai.responses(prompt)
    return _extract_list(response, "sentences", fallback=[source_text])


def extract_actions(sentences: list[str], providers: Providers) -> list[str]:
    if providers.openai is None:
        return [sentence.strip() for sentence in sentences if sentence.strip()]
    prompt = (
        "역할: 행동 규칙 추출기\n"
        "목표: 문장을 행동 단위로 변환\n"
        "출력: actions[] (동사 중심, 짧고 명확)\n"
        "제약: 누락 금지, 중복 제거\n\n"
        f"sentences:\n{sentences}\n"
    )
    response = providers.openai.responses(prompt)
    return _extract_list(response, "actions", fallback=sentences)


def plan_scenes(actions: list[str], duration_seconds: int, slot_seconds: int) -> list[dict[str, Any]]:
    slots = max(1, duration_seconds // slot_seconds)
    scenes: list[dict[str, Any]] = []
    for idx in range(slots):
        start = idx * slot_seconds
        end = min(duration_seconds, start + slot_seconds)
        action = actions[idx % len(actions)] if actions else ""
        scenes.append({"index": idx + 1, "timecode": [start, end], "action": action})
    return scenes


def style_lock(context: PipelineContext, providers: Providers) -> dict[str, Any]:
    if providers.openai is None:
        return {
            "palette": "muted industrial",
            "lighting": "high-contrast warehouse lighting",
            "camera": "steady dolly, 24mm",
            "mood": context.options.get("mood"),
            "site_type": context.options.get("site_type"),
        }
    prompt = (
        "역할: 스타일 락 생성기\n"
        "목표: 캐릭터 외형/복장/색감/조명/렌즈/카메라 규칙을 고정\n"
        "출력: style_lock (불변 규칙 명시)\n\n"
        f"mood:\n{context.options.get('mood')}\n"
        f"site_type:\n{context.options.get('site_type')}\n"
        f"references:\n{context.attachments}\n"
    )
    response = providers.openai.responses(prompt)
    return _extract_object(response, "style_lock", fallback={"mood": context.options.get("mood")})


def beat_map(duration_seconds: int, slot_seconds: int) -> dict[str, Any]:
    segments = []
    for start in range(0, duration_seconds, slot_seconds):
        end = min(duration_seconds, start + slot_seconds)
        segments.append({"start": start, "end": end})
    return {"bpm": 96, "segments": segments}


def clip_prompt(scene: dict[str, Any], style: dict[str, Any]) -> str:
    return (
        f"Action: {scene.get('action')}.\n"
        f"Timecode: {scene.get('timecode')}.\n"
        f"Style: {style}.\n"
        "Cinematic, safety instruction music video."  # short prompt; add details in real mode
    )


def generate_clips(
    scenes: list[dict[str, Any]],
    providers: Providers,
    duration_seconds: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for scene in scenes:
        prompt = scene.get("prompt") or clip_prompt(scene, scene.get("style", {}))
        if providers.sora is None:
            results.append({"scene": scene, "video": {"mock": True, "prompt": prompt, "status": "pending_sora"}})
            continue
        response = providers.sora.generate(prompt, duration_seconds)
        results.append({"scene": scene, "video": response})
    return results


def generate_music(prompt: str, duration_seconds: int, providers: Providers) -> dict[str, Any]:
    if providers.suno is None:
        return {"mock": True, "prompt": prompt, "duration": duration_seconds}
    return providers.suno.generate(prompt, duration_seconds)


def _extract_list(response: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    if isinstance(response, dict):
        candidate = response.get(key)
        if isinstance(candidate, list):
            return [str(item) for item in candidate]
        blob = _extract_json_blob(response)
        if isinstance(blob, dict) and isinstance(blob.get(key), list):
            return [str(item) for item in blob.get(key)]
    return fallback


def _extract_object(response: dict[str, Any], key: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response, dict):
        candidate = response.get(key)
        if isinstance(candidate, dict):
            return candidate
        blob = _extract_json_blob(response)
        if isinstance(blob, dict) and isinstance(blob.get(key), dict):
            return blob.get(key)
    return fallback


def _extract_json_blob(response: dict[str, Any]) -> dict[str, Any] | None:
    text = None
    if isinstance(response.get("output_text"), str):
        text = response.get("output_text")
    if text is None and isinstance(response.get("output"), list):
        # Best-effort extraction from responses output blocks
        blocks = response.get("output", [])
        for block in blocks:
            if isinstance(block, dict):
                content = block.get("content")
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and isinstance(item.get("text"), str):
                            text = item.get("text")
                            break
            if text:
                break
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
