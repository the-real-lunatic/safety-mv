from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from dotenv import load_dotenv
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


class AgenticFlow:
    def __init__(self) -> None:
        self.llm = LLMClient()
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
        return result, trace

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