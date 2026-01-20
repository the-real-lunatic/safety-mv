from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from dotenv import load_dotenv
import httpx
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator, ValidationError
from jsonschema import validate as jsonschema_validate


ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT_DIR / "prompts"
SCHEMA_DIR = ROOT_DIR / "schemas"


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _load_schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


SCHEMAS = {
    "concept": _load_schema("concept.schema.json"),
    "qa": _load_schema("qa_result.schema.json"),
    "blueprint": _load_schema("blueprint.schema.json"),
    "style": _load_schema("style.schema.json"),
    "job_state": _load_schema("job_state.schema.json"),
    "keywords": _load_schema("keywords.schema.json"),
}


class FlowConfig(BaseModel):
    genre: str = Field(default="Hip-hop", min_length=1)
    mood: str = Field(default="Tense → Clear", min_length=1)
    length_seconds: int = Field(default=60, ge=30, le=90)
    llm_model: str = Field(default="gpt-4o-mini", min_length=1)
    llm_temperature: float = Field(default=0.4, ge=0.0, le=1.5)
    hitl_mode: str = Field(default="skip", pattern="^(skip|required)$")


class BlueprintRequest(BaseModel):
    document: str = Field(min_length=1)
    config: FlowConfig


class MVScriptScene(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    description: str
    mood: str | None = None
    lyrics_excerpt: str | None = None


class MVConcept(BaseModel):
    concept_id: str
    lyrics: str
    mv_script: list[MVScriptScene]


class ConceptBatch(BaseModel):
    concepts: list[MVConcept]

    @field_validator("concepts")
    @classmethod
    def _two_concepts_only(cls, value: list[MVConcept]) -> list[MVConcept]:
        if len(value) != 2:
            raise ValueError("Exactly 2 concepts are required")
        return value


class QAResult(BaseModel):
    result: Literal["pass", "fail"]
    score: float
    missing_keywords: list[str] = Field(default_factory=list)
    structural_issues: list[str] = Field(default_factory=list)

class KeywordExtraction(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    keyword_evidence: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("keywords", "key_points")
    @classmethod
    def _limit_length(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]

class TimeRange(BaseModel):
    start: float
    end: float


class LyricsPayload(BaseModel):
    text: str | None = None


class VisualPayload(BaseModel):
    action: str | None = None
    camera: str | None = None


class AudioPayload(BaseModel):
    music_section: str | None = None


class BlueprintScene(BaseModel):
    scene_id: str
    time_range: TimeRange
    lyrics: LyricsPayload
    visual: VisualPayload
    audio: AudioPayload


class MVBlueprint(BaseModel):
    duration: float
    scenes: list[BlueprintScene]


class StyleMetadata(BaseModel):
    character: dict[str, str]
    background: dict[str, str]
    color: dict[str, str]

    @field_validator("character", "background", "color", mode="before")
    @classmethod
    def _coerce_nested_strings(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return value

        def stringify(item: Any) -> str:
            if isinstance(item, (dict, list, tuple)):
                return json.dumps(item, ensure_ascii=False)
            return str(item)

        return {str(key): stringify(val) for key, val in value.items()}


class JobState(BaseModel):
    job_id: str
    state: str
    retry_count: int = 0
    artifacts: dict[str, Any]


class LLMClient:
    def __init__(self) -> None:
        load_dotenv(ROOT_DIR / ".env")
        api_key = os.getenv("GPT_API_KEY")
        if not api_key:
            raise RuntimeError("GPT_API_KEY is missing in environment/.env")
        self.client = OpenAI(api_key=api_key)

    def parse(self, *, model: str, temperature: float, messages: list[dict[str, str]], schema: Any) -> Any:
        if hasattr(self.client, "responses") and hasattr(self.client.responses, "parse"):
            try:
                response = self.client.responses.parse(
                    model=model,
                    input=messages,
                    temperature=temperature,
                    text_format=schema,
                )
                parsed = response.output_parsed
                if parsed is None:
                    raise RuntimeError("LLM response did not return parsed output")
                return parsed
            except Exception:
                pass

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        try:
            if hasattr(schema, "model_validate_json"):
                return schema.model_validate_json(content)
            return schema.parse_raw(content)
        except ValidationError as exc:
            repaired = self._repair_json(
                model=model,
                messages=messages,
                schema=schema,
                content=content,
                error=exc,
            )
            if hasattr(schema, "model_validate_json"):
                return schema.model_validate_json(repaired)
            return schema.parse_raw(repaired)

    def _repair_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        schema: Any,
        content: str,
        error: ValidationError,
    ) -> str:
        schema_json = schema.model_json_schema() if hasattr(schema, "model_json_schema") else {}
        repair_messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict JSON repair agent. "
                    "Return JSON only, matching the provided schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "schema": schema_json,
                        "validation_error": error.errors(),
                        "original_output": content,
                        "original_messages": messages,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        response = self.client.chat.completions.create(
            model=model,
            messages=repair_messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or "{}"


class SoraClient:
    def __init__(self) -> None:
        load_dotenv(ROOT_DIR / ".env")
        self.api_key = os.getenv("SORA_API_KEY")
        self.base_url = os.getenv("SORA_API_BASE", "").rstrip("/")
        if not self.base_url:
            self.base_url = "https://api.openai.com/v1"
        self.image_endpoint = os.getenv("SORA_IMAGE_ENDPOINT", "/images/generations")
        self.asset_endpoint = os.getenv("SORA_ASSET_ENDPOINT", "/images/{asset_id}")
        self.image_model = os.getenv("SORA_IMAGE_MODEL", "gpt-image-1.5")
        self.image_size = os.getenv("SORA_IMAGE_SIZE", "1024x1024")
        self.timeout = float(os.getenv("SORA_TIMEOUT", "60"))
        self._is_openai_images = "api.openai.com" in self.base_url

    @staticmethod
    def _extract_asset_id(data: Any) -> str | None:
        if isinstance(data, dict):
            for key in ("asset_id", "id"):
                if data.get(key):
                    return str(data[key])
            nested = data.get("data")
            if isinstance(nested, dict):
                return nested.get("asset_id") or nested.get("id")
            if isinstance(nested, list) and nested:
                first = nested[0]
                if isinstance(first, dict):
                    return first.get("asset_id") or first.get("id")
        return None

    @staticmethod
    def _extract_asset_url(data: Any) -> str | None:
        if isinstance(data, dict):
            for key in ("url", "image_url", "output_url"):
                if data.get(key):
                    return str(data[key])
            nested = data.get("data")
            if isinstance(nested, dict):
                for key in ("url", "image_url", "output_url"):
                    if nested.get(key):
                        return str(nested[key])
            if isinstance(nested, list) and nested:
                first = nested[0]
                if isinstance(first, dict):
                    for key in ("url", "image_url", "output_url"):
                        if first.get(key):
                            return str(first[key])
        return None

    @staticmethod
    def _extract_b64(data: Any) -> str | None:
        if isinstance(data, dict):
            nested = data.get("data")
            if isinstance(nested, list) and nested:
                first = nested[0]
                if isinstance(first, dict):
                    b64 = first.get("b64_json")
                    if b64:
                        return str(b64)
        return None

    def _build_asset_url(self, asset_id: str) -> str:
        path = self.asset_endpoint
        if "{asset_id}" in path:
            path = path.format(asset_id=asset_id)
        else:
            path = f"{path.rstrip('/')}/{asset_id}"
        return f"{self.base_url}{path}"

    def create_image(self, prompt: str) -> dict[str, Any]:
        if not self.api_key or not self.base_url:
            return {
                "status": "mock",
                "asset_id": f"asset_{uuid4().hex[:10]}",
                "detail": "SORA_API_KEY or SORA_API_BASE missing",
            }

        url = f"{self.base_url}{self.image_endpoint}"
        payload = {"prompt": prompt, "type": "image"}
        if self._is_openai_images:
            payload = {
                "prompt": prompt,
                "model": self.image_model,
                "size": self.image_size,
            }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            asset_id = self._extract_asset_id(data)
            if not asset_id:
                asset_id = f"asset_{uuid4().hex[:10]}"
            b64_json = self._extract_b64(data)
            return {
                "status": "ready" if b64_json else "submitted",
                "asset_id": asset_id,
                "b64_json": b64_json,
                "response": data,
            }
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            return {
                "status": "error",
                "asset_id": None,
                "detail": detail,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "asset_id": None,
                "detail": str(exc),
            }

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        if not self.api_key or not self.base_url:
            return {
                "status": "mock",
                "asset_id": asset_id,
                "detail": "SORA_API_KEY or SORA_API_BASE missing",
            }
        if self._is_openai_images:
            return {
                "status": "not_supported",
                "asset_id": asset_id,
                "detail": "OpenAI images API does not support asset retrieval.",
            }
        url = self._build_asset_url(asset_id)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = httpx.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            if response.headers.get("content-type", "").startswith("image/"):
                return {
                    "status": "ready",
                    "asset_id": asset_id,
                    "content_type": response.headers.get("content-type"),
                    "binary": response.content,
                }
            data = response.json()
            asset_url = self._extract_asset_url(data)
            return {
                "status": "ready",
                "asset_id": asset_id,
                "url": asset_url,
                "response": data,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "asset_id": asset_id,
                "detail": str(exc),
            }

    def fetch_image(self, asset_id: str) -> tuple[bytes | None, str | None]:
        if not self.api_key or not self.base_url:
            return None, None
        if self._is_openai_images:
            return None, None
        result = self.get_asset(asset_id)
        if result.get("binary") is not None:
            return result["binary"], result.get("content_type") or "image/png"
        asset_url = result.get("url")
        if not asset_url:
            return None, None
        try:
            response = httpx.get(asset_url, timeout=self.timeout)
            response.raise_for_status()
            content_type = response.headers.get("content-type") or "image/png"
            return response.content, content_type
        except Exception:  # noqa: BLE001
            return None, None


class AgenticFlow:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.sora = SoraClient()
        self.prompts = {
            "concept_gen": _load_text(PROMPT_DIR / "concept_gen.md"),
            "keyword_extractor": _load_text(PROMPT_DIR / "keyword_extractor.md"),
            "qa_scorer": _load_text(PROMPT_DIR / "qa_scorer.md"),
            "blueprint_assembler": _load_text(PROMPT_DIR / "blueprint_assembler.md"),
            "style_binder": _load_text(PROMPT_DIR / "style_binder.md"),
        }

    def _validate_schema(self, schema_name: str, payload: Any) -> None:
        jsonschema_validate(payload, SCHEMAS[schema_name])

    @staticmethod
    def _chunk_document(text: str, max_chars: int = 1200, max_chunks: int = 6) -> list[str]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        chunks: list[str] = []
        buffer = ""
        for line in lines:
            if len(buffer) + len(line) + 1 > max_chars and buffer:
                chunks.append(buffer)
                buffer = line
            else:
                buffer = f"{buffer}\n{line}".strip()
            if len(chunks) >= max_chunks:
                break
        if buffer and len(chunks) < max_chunks:
            chunks.append(buffer)
        if not chunks:
            return [text[:max_chars]]
        return chunks

    def _extract_keywords(self, document: str, config: FlowConfig) -> tuple[KeywordExtraction, list[dict[str, Any]]]:
        chunks = self._chunk_document(document)
        all_keywords: list[str] = []
        all_points: list[str] = []
        traces: list[dict[str, Any]] = []
        for idx, chunk in enumerate(chunks, start=1):
            user_prompt = (
                f"문서 일부({idx}/{len(chunks)}):\n{chunk}\n\n"
                "JSON 필드: keywords[], key_points[]"
            )
            messages = [
                {"role": "system", "content": self.prompts["keyword_extractor"]},
                {"role": "user", "content": user_prompt},
            ]
            result = self.llm.parse(
                model=config.llm_model,
                temperature=0.1,
                messages=messages,
                schema=KeywordExtraction,
            )
            self._validate_schema("keywords", result.model_dump(exclude_none=True))
            all_keywords.extend(result.keywords)
            all_points.extend(result.key_points)
            traces.append(
                {
                    "step": "KEYWORD_EXTRACTOR",
                    "chunk": idx,
                    "model": config.llm_model,
                    "temperature": 0.1,
                    "messages": messages,
                    "output": result.model_dump(),
                }
            )
        dedup_keywords = list(dict.fromkeys([item.strip() for item in all_keywords if item.strip()]))
        dedup_points = list(dict.fromkeys([item.strip() for item in all_points if item.strip()]))
        keyword_evidence = self._build_keyword_evidence(dedup_keywords[:12], chunks)
        summary = KeywordExtraction(
            keywords=dedup_keywords[:12],
            key_points=dedup_points[:14],
            keyword_evidence=keyword_evidence,
        )
        return summary, traces

    def _build_keyword_evidence(self, keywords: list[str], chunks: list[str]) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []
        for keyword in keywords:
            sources: list[dict[str, Any]] = []
            for idx, chunk in enumerate(chunks, start=1):
                start = 0
                while True:
                    pos = chunk.find(keyword, start)
                    if pos == -1:
                        break
                    sources.append(
                        {
                            "page_number": idx,
                            "start_offset": pos,
                            "end_offset": pos + len(keyword),
                            "text": self._extract_sentence(chunk, pos),
                        }
                    )
                    if len(sources) >= 3:
                        break
                    start = pos + len(keyword)
                if len(sources) >= 3:
                    break
            evidence.append({"keyword": keyword, "sources": sources})
        return evidence

    @staticmethod
    def _extract_sentence(text: str, pos: int) -> str:
        if not text:
            return ""
        left = max(
            text.rfind(".", 0, pos),
            text.rfind("!", 0, pos),
            text.rfind("?", 0, pos),
            text.rfind("\n", 0, pos),
        )
        right_candidates = [
            text.find(".", pos),
            text.find("!", pos),
            text.find("?", pos),
            text.find("\n", pos),
        ]
        right_candidates = [idx for idx in right_candidates if idx != -1]
        right = min(right_candidates) if right_candidates else len(text)
        start = left + 1 if left != -1 else 0
        end = right + 1 if right < len(text) else len(text)
        return text[start:end].strip()

    def _concept_gen(
        self,
        document: str,
        keywords: KeywordExtraction,
        config: FlowConfig,
        feedback: str | None = None,
    ) -> tuple[ConceptBatch, dict[str, Any]]:
        summary_text = (
            f"키워드: {', '.join(keywords.keywords)}\n"
            f"핵심 행동: {' | '.join(keywords.key_points)}\n"
            f"문서 요약: {document[:400]}"
        )
        user_prompt = (
            f"장르: {config.genre}\n"
            f"분위기: {config.mood}\n"
            f"길이(초): {config.length_seconds}\n"
            f"{summary_text}\n"
        )
        if feedback:
            user_prompt += f"\n재시도 피드백: {feedback}\n"
        user_prompt += (
            "\n반드시 concepts 배열에 2개 후보를 JSON으로 출력하라."
            "\n각 concept는 concept_id, lyrics, mv_script를 포함해야 한다."
            "\nmv_script는 start, end, description을 포함하는 객체 배열이다."
            "\n출력 예시: {\"concepts\":[{\"concept_id\":\"c1\",\"lyrics\":\"...\",\"mv_script\":[{\"start\":0,\"end\":5,\"description\":\"...\"}]}]}"
            "\n가사는 반드시 한국어로만 작성하라."
        )

        messages = [
            {"role": "system", "content": self.prompts["concept_gen"]},
            {"role": "user", "content": user_prompt},
        ]
        result = self.llm.parse(
            model=config.llm_model,
            temperature=config.llm_temperature,
            messages=messages,
            schema=ConceptBatch,
        )
        for concept in result.concepts:
            self._validate_schema("concept", concept.model_dump(exclude_none=True))
        trace = {
            "step": "CONCEPT_GEN",
            "model": config.llm_model,
            "temperature": config.llm_temperature,
            "messages": messages,
            "output": result.model_dump(),
        }
        return result, trace

    def _qa_score(
        self,
        document_summary: KeywordExtraction,
        concept: MVConcept,
        config: FlowConfig,
    ) -> tuple[QAResult, dict[str, Any]]:
        summary_text = (
            f"키워드: {', '.join(document_summary.keywords)}\n"
            f"핵심 행동: {' | '.join(document_summary.key_points)}\n"
        )
        user_prompt = (
            f"{summary_text}"
            f"컨셉 JSON: {concept.model_dump_json()}\n"
            "문서의 핵심 행동/키워드가 의미적으로 반영되었는지 평가하라."
            "가사/연출에 일부 표현이라도 의도가 담겨 있으면 포함으로 본다."
        )
        user_prompt += (
            "\nJSON에는 result(pass|fail), score(0-1), missing_keywords[], structural_issues[]만 포함하라."
        )
        messages = [
            {"role": "system", "content": self.prompts["qa_scorer"]},
            {"role": "user", "content": user_prompt},
        ]
        result = self.llm.parse(
            model=config.llm_model,
            temperature=0,
            messages=messages,
            schema=QAResult,
        )
        self._validate_schema("qa", result.model_dump(exclude_none=True))
        trace = {
            "step": "QA",
            "model": config.llm_model,
            "temperature": 0,
            "messages": messages,
            "output": result.model_dump(),
            "concept_id": concept.concept_id,
        }
        return result, trace

    def _assemble_blueprint(
        self,
        concept: MVConcept,
        config: FlowConfig,
    ) -> tuple[MVBlueprint, dict[str, Any]]:
        user_prompt = (
            f"선택된 컨셉 JSON: {concept.model_dump_json()}\n"
            f"영상 길이: {config.length_seconds}초"
        )
        user_prompt += "\nJSON에는 duration과 scenes 배열만 포함하라."
        messages = [
            {"role": "system", "content": self.prompts["blueprint_assembler"]},
            {"role": "user", "content": user_prompt},
        ]
        result = self.llm.parse(
            model=config.llm_model,
            temperature=0,
            messages=messages,
            schema=MVBlueprint,
        )
        self._validate_schema("blueprint", result.model_dump(exclude_none=True))
        trace = {
            "step": "LOCK_BLUEPRINT_CORE",
            "model": config.llm_model,
            "temperature": 0,
            "messages": messages,
            "output": result.model_dump(),
        }
        fixed = self._ensure_scene_duration(result, config)
        if fixed is not None:
            trace["repair"] = True
            trace["repair_output"] = fixed.model_dump()
            return fixed, trace
        return result, trace

    @staticmethod
    def _scene_duration(scene: BlueprintScene) -> float:
        return max(0.0, scene.time_range.end - scene.time_range.start)

    def _ensure_scene_duration(self, blueprint: MVBlueprint, config: FlowConfig) -> MVBlueprint | None:
        violations = [
            scene
            for scene in blueprint.scenes
            if self._scene_duration(scene) > 10.0
        ]
        if not violations:
            return None
        user_prompt = (
            f"Blueprint JSON: {blueprint.model_dump_json()}\\n"
            f"영상 길이: {config.length_seconds}초\\n"
            "규칙: 모든 scene의 end-start는 10초 이내여야 한다.\\n"
            "scene 순서를 유지하고 scene 개수는 변경하지 마라.\\n"
            "start/end는 오름차순으로 정렬하고 전체 duration을 유지하라."
        )
        messages = [
            {"role": "system", "content": "You fix blueprint timing. Return JSON only."},
            {"role": "user", "content": user_prompt},
        ]
        fixed = self.llm.parse(
            model=config.llm_model,
            temperature=0,
            messages=messages,
            schema=MVBlueprint,
        )
        self._validate_schema("blueprint", fixed.model_dump(exclude_none=True))
        if any(self._scene_duration(scene) > 10.0 for scene in fixed.scenes):
            raise RuntimeError("Blueprint validation failed: scene duration > 10s")
        return fixed

    def _bind_style(
        self,
        blueprint: MVBlueprint,
        config: FlowConfig,
    ) -> tuple[StyleMetadata, dict[str, Any]]:
        user_prompt = (
            f"Blueprint JSON: {blueprint.model_dump_json()}\n"
            f"장르: {config.genre}\n"
            f"분위기: {config.mood}\n"
            "일관된 캐릭터/배경/색감 규칙을 JSON으로 고정하라."
        )
        user_prompt += "\nJSON에는 character/background/color 객체만 포함하라."
        messages = [
            {"role": "system", "content": self.prompts["style_binder"]},
            {"role": "user", "content": user_prompt},
        ]
        result = self.llm.parse(
            model=config.llm_model,
            temperature=0.2,
            messages=messages,
            schema=StyleMetadata,
        )
        self._validate_schema("style", result.model_dump(exclude_none=True))
        trace = {
            "step": "STYLE_BIND",
            "model": config.llm_model,
            "temperature": 0.2,
            "messages": messages,
            "output": result.model_dump(),
        }
        return result, trace

    @staticmethod
    def _build_media_plan(
        blueprint: MVBlueprint,
        style: StyleMetadata,
        character_asset: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base_style = AgenticFlow._build_style_base(style)
        character_prompt = AgenticFlow._build_character_prompt(style)
        asset_id = character_asset.get("asset_id") if character_asset else None
        character_job = {
            "job_id": "character_ref",
            "provider": "sora",
            "api_key_env": "SORA_API_KEY",
            "type": "image",
            "prompt": character_prompt,
            "asset_id": asset_id,
            "status": character_asset.get("status") if character_asset else None,
        }
        video_jobs = []
        for scene in blueprint.scenes:
            duration = max(1, int(scene.time_range.end - scene.time_range.start))
            prompt = (
                f"{base_style}. "
                f"visual action: {scene.visual.action if scene.visual else ''}. "
                f"camera: {scene.visual.camera if scene.visual else ''}. "
                f"lyrics: {scene.lyrics.text if scene.lyrics else ''}."
            ).strip()
            video_jobs.append(
                {
                    "scene_id": scene.scene_id,
                    "provider": "sora",
                    "api_key_env": "SORA_API_KEY",
                    "type": "video",
                    "duration_seconds": duration,
                    "prompt": prompt,
                    "character_reference": "character_ref",
                    "character_asset_id": asset_id,
                }
            )
        return {
            "character_asset_id": asset_id,
            "character_job": character_job,
            "video_jobs": video_jobs,
            "music_job": {
                "provider": "suno",
                "api_key_env": "SUNO_API_KEY",
                "prompt": "Generate music that matches the blueprint mood and timing.",
            },
        }

    @staticmethod
    def _build_style_base(style: StyleMetadata) -> str:
        return (
            f"character: {style.character.get('appearance', '')}, outfit: {style.character.get('outfit', '')}; "
            f"background: {style.background.get('environment', '')}, lighting: {style.background.get('lighting', '')}; "
            f"color: {style.color.get('primary', '')}/{style.color.get('secondary', '')}"
        )

    @classmethod
    def _build_character_prompt(cls, style: StyleMetadata) -> str:
        base_style = cls._build_style_base(style)
        return (
            "Create a single character reference image. "
            f"{base_style}. "
            "Neutral pose, full body, front view, plain background."
        ).strip()

    def _generate_character_asset(
        self,
        style: StyleMetadata,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        prompt = self._build_character_prompt(style)
        response = self.sora.create_image(prompt)
        preview_url = None
        if response.get("b64_json"):
            preview_url = f"data:image/png;base64,{response['b64_json']}"
        elif isinstance(response.get("response"), dict):
            preview_url = self.sora._extract_asset_url(response.get("response"))
        asset = {
            "provider": "sora",
            "asset_id": response.get("asset_id"),
            "status": response.get("status"),
            "prompt": prompt,
        }
        if response.get("b64_json"):
            asset["preview_b64"] = response["b64_json"]
        if preview_url:
            asset["preview_url"] = preview_url
        if response.get("detail"):
            asset["detail"] = response["detail"]
        trace = {
            "step": "CHARACTER_IMAGE_GEN",
            "provider": "sora",
            "prompt": prompt,
            "output": response,
        }
        return asset, trace

    @staticmethod
    def _select_best(concepts: list[MVConcept], qa_results: list[QAResult]) -> int:
        indexed = list(enumerate(qa_results))
        indexed.sort(key=lambda item: (item[1].result != "pass", -item[1].score))
        return indexed[0][0]

    def _build_job_response(
        self,
        job_id: str,
        state: str,
        retry_count: int,
        artifacts: dict[str, Any],
        state_history: list[str],
        trace: list[dict[str, Any]],
        hitl_payload: dict[str, Any],
    ) -> dict[str, Any]:
        job_state = JobState(
            job_id=job_id,
            state=state,
            retry_count=retry_count,
            artifacts=artifacts,
        )
        self._validate_schema("job_state", job_state.model_dump(exclude_none=True))
        return {
            "job": job_state.model_dump(),
            "hitl": hitl_payload,
            "state_history": state_history,
            "trace": trace,
        }

    def run(self, payload: BlueprintRequest) -> dict[str, Any]:
        job_id = f"job_{uuid4().hex[:8]}"
        retry_count = 0
        state_history: list[str] = ["INIT"]
        trace: list[dict[str, Any]] = []

        keyword_summary, keyword_traces = self._extract_keywords(payload.document, payload.config)
        trace.extend(keyword_traces)
        concepts, concept_trace = self._concept_gen(payload.document, keyword_summary, payload.config)
        state_history.append("CONCEPT_GEN")
        trace.append(concept_trace)

        qa_results: list[QAResult] = []
        for concept in concepts.concepts:
            qa_result, qa_trace = self._qa_score(keyword_summary, concept, payload.config)
            qa_results.append(qa_result)
            trace.append(qa_trace)
        state_history.append("QA")

        if all(result.result == "fail" for result in qa_results) and retry_count < 1:
            retry_count += 1
            feedback = {
                "missing_keywords": sorted({kw for result in qa_results for kw in result.missing_keywords}),
                "structural_issues": sorted({issue for result in qa_results for issue in result.structural_issues}),
            }
            keyword_summary, keyword_traces = self._extract_keywords(payload.document, payload.config)
            trace.extend(keyword_traces)
            concepts, concept_trace = self._concept_gen(
                payload.document,
                keyword_summary,
                payload.config,
                feedback=json.dumps(feedback, ensure_ascii=False),
            )
            state_history.append("CONCEPT_GEN")
            concept_trace["step"] = "RETRY_CONCEPT_GEN"
            trace.append(concept_trace)
            qa_results = []
            for concept in concepts.concepts:
                qa_result, qa_trace = self._qa_score(keyword_summary, concept, payload.config)
                qa_results.append(qa_result)
                qa_trace["step"] = "RETRY_QA"
                trace.append(qa_trace)
            state_history.append("QA")

        selected_index = self._select_best(concepts.concepts, qa_results)
        selected_concept = concepts.concepts[selected_index]

        state_history.append("HITL")
        hitl_payload = {
            "requires_human": payload.config.hitl_mode == "required",
            "selected_concept_id": selected_concept.concept_id,
        }

        if payload.config.hitl_mode == "required":
            return self._build_job_response(
                job_id=job_id,
                state="HITL",
                retry_count=retry_count,
                artifacts={
                    "extracted_keywords": keyword_summary.keywords,
                    "key_points": keyword_summary.key_points,
                    "keyword_evidence": keyword_summary.keyword_evidence,
                    "concepts": [c.model_dump() for c in concepts.concepts],
                    "qa_results": [r.model_dump() for r in qa_results],
                    "selected_concept": selected_concept.model_dump(),
                },
                state_history=state_history,
                trace=trace,
                hitl_payload=hitl_payload,
            )

        return self._continue_after_hitl(
            job_id=job_id,
            document=payload.document,
            config=payload.config,
            selected_concept=selected_concept,
            concepts=concepts.concepts,
            qa_results=qa_results,
            retry_count=retry_count,
            state_history=state_history,
            trace=trace,
            hitl_payload=hitl_payload,
            keyword_summary=keyword_summary,
        )

    def _continue_after_hitl(
        self,
        *,
        job_id: str,
        document: str,
        config: FlowConfig,
        selected_concept: MVConcept,
        concepts: list[MVConcept],
        qa_results: list[QAResult],
        retry_count: int,
        state_history: list[str],
        trace: list[dict[str, Any]],
        hitl_payload: dict[str, Any],
        keyword_summary: KeywordExtraction,
    ) -> dict[str, Any]:
        blueprint, blueprint_trace = self._assemble_blueprint(selected_concept, config)
        state_history.append("LOCK_BLUEPRINT_CORE")
        trace.append(blueprint_trace)

        style, style_trace = self._bind_style(blueprint, config)
        state_history.append("STYLE_BIND")
        trace.append(style_trace)
        character_asset, character_trace = self._generate_character_asset(style)
        state_history.append("CHARACTER_IMAGE_GEN")
        trace.append(character_trace)
        media_plan = self._build_media_plan(blueprint, style, character_asset)

        return self._build_job_response(
            job_id=job_id,
            state="STYLE_BIND",
            retry_count=retry_count,
            artifacts={
                "extracted_keywords": keyword_summary.keywords,
                "key_points": keyword_summary.key_points,
                "keyword_evidence": keyword_summary.keyword_evidence,
                "concepts": [c.model_dump() for c in concepts],
                "qa_results": [r.model_dump() for r in qa_results],
                "selected_concept": selected_concept.model_dump(),
                "blueprint": blueprint.model_dump(),
                "style": style.model_dump(),
                "character_asset": character_asset,
                "media_plan": media_plan,
                "document": document,
                "config": config.model_dump(),
            },
            state_history=state_history,
            trace=trace,
            hitl_payload=hitl_payload,
        )

    def continue_from_hitl(
        self,
        *,
        job_id: str,
        document: str,
        config: FlowConfig,
        selected_concept: MVConcept,
        concepts: list[MVConcept],
        qa_results: list[QAResult],
        retry_count: int,
        state_history: list[str],
        trace: list[dict[str, Any]],
        hitl_payload: dict[str, Any],
        keyword_summary: KeywordExtraction,
    ) -> dict[str, Any]:
        return self._continue_after_hitl(
            job_id=job_id,
            document=document,
            config=config,
            selected_concept=selected_concept,
            concepts=concepts,
            qa_results=qa_results,
            retry_count=retry_count,
            state_history=state_history,
            trace=trace,
            hitl_payload=hitl_payload,
            keyword_summary=keyword_summary,
        )
