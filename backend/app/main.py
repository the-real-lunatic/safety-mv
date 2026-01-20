from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import io

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from minio import Minio
from pydantic import BaseModel, Field
import redis

from .agentic_flow import (
    AgenticFlow,
    BlueprintRequest,
    FlowConfig,
    MVConcept,
    MVScriptScene,
    QAResult,
    KeywordExtraction,
)
from pypdf import PdfReader

app = FastAPI(
    title="SafetyMV Backend",
    version="0.1.0",
    description="Infra-only backend with health checks.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK_NOTICE = "infra-only scaffold (mock outputs, no model/pipeline logic)"
DEFAULT_GENRE = "Hip-hop"
DEFAULT_MOOD = "Tense → Clear"
DEFAULT_VISUAL_STYLE = "K-webtoon"
_AGENTIC_FLOW: AgenticFlow | None = None
JOB_TTL_SECONDS = 60 * 60 * 6


def _get_agentic_flow() -> AgenticFlow:
    global _AGENTIC_FLOW
    if _AGENTIC_FLOW is None:
        _AGENTIC_FLOW = AgenticFlow()
    return _AGENTIC_FLOW


def _job_key(job_id: str) -> str:
    return f"safety_mv:job:{job_id}"


def _save_job(job_id: str, payload: dict[str, Any]) -> None:
    client = _get_redis_client()
    client.set(_job_key(job_id), json.dumps(payload, ensure_ascii=False), ex=JOB_TTL_SECONDS)


def _load_job(job_id: str) -> dict[str, Any] | None:
    client = _get_redis_client()
    raw = client.get(_job_key(job_id))
    if not raw:
        return None
    return json.loads(raw)


def _update_job(job_id: str, **updates: Any) -> dict[str, Any]:
    job = _load_job(job_id) or {"job_id": job_id}
    job.update(updates)
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_job(job_id, job)
    return job


def _get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _get_minio_client() -> Minio:
    return Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )


class PreviewFlowConfig(BaseModel):
    length_seconds: int = Field(default=60, ge=30, le=90)
    mood: str = Field(default=DEFAULT_MOOD, min_length=1)
    genre: str = Field(default=DEFAULT_GENRE, min_length=1)
    visual_style: str = Field(default=DEFAULT_VISUAL_STYLE, min_length=1)
    options: int = Field(default=3, ge=2, le=3)
    llm_provider: str = Field(default="openai", min_length=1)
    llm_model: str = Field(default="gpt-4o-mini", min_length=1)
    llm_temperature: float = Field(default=0.4, ge=0.0, le=1.5)


class FlowRequest(BaseModel):
    document: str = Field(min_length=1)
    config: PreviewFlowConfig | None = None


def _normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def _build_llm_plan(document_preview: str, config: PreviewFlowConfig) -> dict[str, Any]:
    system_base = (
        "You are a SafetyMV agent. Return strict JSON only. "
        "Do not add commentary or markdown."
    )
    user_doc = f"Document (preview): {document_preview}"

    return {
        "provider": config.llm_provider,
        "model": config.llm_model,
        "temperature": config.llm_temperature,
        "calls": [
            {
                "id": "doc_parser",
                "agent": "Doc Parser",
                "purpose": "Split document into atomic safety statements.",
                "messages": [
                    {"role": "system", "content": system_base},
                    {
                        "role": "user",
                        "content": f"{user_doc}\n\nExtract 8-12 short statements.",
                    },
                ],
                "expected_output": {"doc_segments": ["..."]},
            },
            {
                "id": "action_extractor",
                "agent": "Action Extractor",
                "purpose": "Convert statements into action cards.",
                "depends_on": ["doc_parser"],
                "messages": [
                    {"role": "system", "content": system_base},
                    {
                        "role": "user",
                        "content": "From doc_segments, extract action cards with text + intent.",
                    },
                ],
                "expected_output": {"action_cards": [{"text": "...", "intent": "..."}]},
            },
            {
                "id": "action_classifier",
                "agent": "Action Classifier",
                "purpose": "Classify actions into fixed types.",
                "depends_on": ["action_extractor"],
                "messages": [
                    {"role": "system", "content": system_base},
                    {
                        "role": "user",
                        "content": "Map each action card to type: 착용/확인/금지/주의/보고/기타.",
                    },
                ],
                "expected_output": {"action_cards": [{"text": "...", "type": "..."}]},
            },
        ],
        "pev_loop": {
            "rounds": config.options,
            "agents": [
                {
                    "role": "Planner",
                    "goal": "Propose scene flow skeleton (intro/outro + key beats).",
                    "messages": [
                        {"role": "system", "content": system_base},
                        {
                            "role": "user",
                            "content": (
                                "Given action_cards, outline a scene plan for a safety MV."
                            ),
                        },
                    ],
                    "expected_output": {"scene_plan": ["..."]},
                },
                {
                    "role": "Executor",
                    "goal": "Turn scene plan into timecoded shots.",
                    "messages": [
                        {"role": "system", "content": system_base},
                        {
                            "role": "user",
                            "content": "Expand scene_plan into timecoded shots with short visuals.",
                        },
                    ],
                    "expected_output": {"scene_plan": [{"time": "...", "visual": "..."}]},
                },
                {
                    "role": "Verifier",
                    "goal": "Check missing safety actions and tone consistency.",
                    "messages": [
                        {"role": "system", "content": system_base},
                        {
                            "role": "user",
                            "content": (
                                "Verify all action_cards appear in scene_plan. "
                                "Return missing items + fixes."
                            ),
                        },
                    ],
                    "expected_output": {
                        "missing_actions": ["..."],
                        "fixes": ["..."],
                    },
                },
            ],
            "handoff": "Planner → Executor → Verifier, loop repeats until verified.",
        },
        "downstream_calls": [
            {
                "id": "lyrics_generator",
                "agent": "Hook Generator",
                "purpose": "Generate 2-3 short lyric options per scene.",
                "depends_on": ["action_classifier", "pev_loop"],
                "messages": [
                    {"role": "system", "content": system_base},
                    {
                        "role": "user",
                        "content": (
                            "Create lyric hooks aligned to the final scene plan."
                        ),
                    },
                ],
                "expected_output": {"options": [{"lyrics": ["..."]}]},
            },
            {
                "id": "video_script_generator",
                "agent": "Visual Prompt Builder",
                "purpose": "Generate short video script lines per option.",
                "depends_on": ["pev_loop"],
                "messages": [
                    {"role": "system", "content": system_base},
                    {
                        "role": "user",
                        "content": (
                            "Create concise video script lines (scene-by-scene)."
                        ),
                    },
                ],
                "expected_output": {"options": [{"video_script": ["..."]}]},
            },
        ],
    }


def _build_placeholder_outputs(options: int, config: PreviewFlowConfig) -> dict[str, Any]:
    placeholder_action = {
        "text": "LLM output pending (action card)",
        "type": "pending",
    }
    placeholder_scene = {
        "time": "00-00s",
        "title": "Scene",
        "beat": "pending",
        "visual": "LLM output pending (scene plan)",
    }
    placeholder_option = {
        "option_id": "A",
        "title": f"Option A · {config.genre}",
        "lyrics": ["LLM output pending"],
        "video_script": ["LLM output pending"],
    }
    return {
        "doc_segments": ["LLM output pending (doc segments)"],
        "action_cards": [placeholder_action],
        "scene_plan": [placeholder_scene],
        "options": [
            {
                **placeholder_option,
                "option_id": chr(ord("A") + idx),
                "title": f"Option {chr(ord('A') + idx)} · {config.genre}",
            }
            for idx in range(options)
        ],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.get("/health/redis")
def health_redis() -> JSONResponse:
    try:
        client = _get_redis_client()
        pong = client.ping()
        if pong is True:
            return JSONResponse({"status": "ok"})
        return JSONResponse({"status": "degraded", "detail": "ping failed"}, status_code=503)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "down", "detail": str(exc)}, status_code=503)


@app.get("/health/minio")
def health_minio() -> JSONResponse:
    try:
        client = _get_minio_client()
        # A lightweight call to verify connectivity/auth
        list(client.list_buckets())
        return JSONResponse({"status": "ok"})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"status": "down", "detail": str(exc)}, status_code=503)


@app.post("/flow/preview")
def preview_flow(payload: FlowRequest) -> dict[str, Any]:
    config = payload.config or PreviewFlowConfig()
    document_preview = _normalize_text(payload.document)[:240]
    llm_plan = _build_llm_plan(document_preview, config)
    placeholders = _build_placeholder_outputs(config.options, config)
    agents = [
        {"name": "Doc Parser", "status": "pending", "output": "doc_segments"},
        {"name": "Action Extractor", "status": "pending", "output": "action_cards"},
        {"name": "Action Classifier", "status": "pending", "output": "action_cards"},
        {"name": "Scene Planner", "status": "pending", "output": "scene_plan"},
        {"name": "Hook Generator", "status": "pending", "output": "options"},
        {"name": "Visual Prompt Builder", "status": "pending", "output": "scene_plan"},
        {"name": "Music Planner", "status": "pending", "output": "global_music"},
    ]

    return {
        "flow_id": f"flow_{uuid4().hex[:8]}",
        "status": "mocked",
        "notice": MOCK_NOTICE,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "document_preview": document_preview,
            "config": config.model_dump(),
        },
        "intermediate": {
            "doc_segments": placeholders["doc_segments"],
            "action_cards": placeholders["action_cards"],
            "scene_plan": placeholders["scene_plan"],
            "global_music": {
                "length_seconds": config.length_seconds,
                "genre": config.genre,
                "mood": config.mood,
            },
        },
        "agents": agents,
        "pev_loop": [
            {
                "round": str(idx + 1),
                "plan": "LLM Planner pending",
                "execute": "LLM Executor pending",
                "verify": "LLM Verifier pending",
            }
            for idx in range(config.options)
        ],
        "llm_plan": llm_plan,
        "options": placeholders["options"],
    }


def _parse_length(value: str | int) -> int:
    if isinstance(value, int):
        return value
    if value.endswith("s"):
        return int(value[:-1])
    return int(value)


class JobCreateRequest(BaseModel):
    guidelines: str = Field(default="")
    length: str = Field(default="60s")
    selectedStyles: list[str] = Field(default_factory=list)
    selectedGenres: str = Field(default="hiphop")
    additionalRequirements: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")
    llm_temperature: float = Field(default=0.4)
    hitl_mode: str = Field(default="skip")


def _build_document(guidelines: str, additional: str) -> str:
    if additional:
        return f"{guidelines}\n\n추가 요구사항: {additional}".strip()
    return guidelines.strip()


def _enqueue_job(payload: BlueprintRequest) -> str:
    job_id = f"job_{uuid4().hex[:8]}"
    _save_job(
        job_id,
        {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
            "payload": {
                "document": payload.document,
                "config": payload.config.model_dump(),
            },
        },
    )
    return job_id


def _run_job(job_id: str) -> None:
    job = _load_job(job_id)
    if not job:
        return
    _update_job(job_id, status="running", progress=0.1)
    payload_data = job.get("payload", {})
    payload = BlueprintRequest(
        document=payload_data.get("document", ""),
        config=FlowConfig.model_validate(payload_data.get("config", {})),
    )
    try:
        response = _get_agentic_flow().run(payload)
        artifacts = response.get("job", {}).get("artifacts", {})
        keywords = artifacts.get("extracted_keywords", [])
        pages = job.get("pdf_pages") or [{"page_number": 1, "text": payload.document}]
        artifacts["keyword_evidence"] = _build_keyword_evidence_from_pages(keywords, pages)
        if "job" in response:
            response["job"]["artifacts"] = artifacts
        state = response.get("job", {}).get("state")
        status = "completed" if state != "HITL" else "hitl_required"
        _update_job(
            job_id,
            status=status,
            progress=1.0 if status == "completed" else 0.8,
            result=response,
        )
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, status="failed", progress=1.0, error=str(exc))


@app.post("/flow/blueprint")
def generate_blueprint(payload: BlueprintRequest) -> dict[str, Any]:
    try:
        return _get_agentic_flow().run(payload)
    except RuntimeError as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/jobs")
def create_job(payload: JobCreateRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    document = _build_document(payload.guidelines, payload.additionalRequirements)
    if not document:
        raise HTTPException(status_code=400, detail="guidelines required")
    config = FlowConfig(
        genre=payload.selectedGenres,
        mood=", ".join(payload.selectedStyles) if payload.selectedStyles else "default",
        length_seconds=_parse_length(payload.length),
        llm_model=payload.llm_model,
        llm_temperature=payload.llm_temperature,
        hitl_mode=payload.hitl_mode,
    )
    job_id = _enqueue_job(BlueprintRequest(document=document, config=config))
    job = _load_job(job_id) or {}
    job["pdf_pages"] = [{"page_number": 0, "text": document}]
    _save_job(job_id, job)
    background_tasks.add_task(_run_job, job_id)
    return {"job_id": job_id}


@app.post("/jobs/upload")
async def create_job_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    guidelines: str = Form(""),
    length: str = Form("60s"),
    selectedStyles: str = Form(""),
    selectedGenres: str = Form("hiphop"),
    additionalRequirements: str = Form(""),
    llm_model: str = Form("gpt-4o-mini"),
    llm_temperature: float = Form(0.4),
    hitl_mode: str = Form("skip"),
) -> dict[str, Any]:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF only")
    contents = await file.read()
    pages = _extract_pdf_pages(contents)
    pdf_text = "\n".join(page["text"] for page in pages).strip()
    if not pdf_text:
        raise HTTPException(status_code=400, detail="PDF text extraction failed")
    styles = [style.strip() for style in selectedStyles.split(",") if style.strip()]
    base_document = pdf_text
    if guidelines:
        base_document = f"{pdf_text}\n{guidelines}"
    document = _build_document(base_document, additionalRequirements)
    config = FlowConfig(
        genre=selectedGenres,
        mood=", ".join(styles) if styles else "default",
        length_seconds=_parse_length(length),
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        hitl_mode=hitl_mode,
    )
    job_id = _enqueue_job(BlueprintRequest(document=document, config=config))
    job = _load_job(job_id) or {}
    if guidelines:
        pages.append({"page_number": 0, "text": guidelines})
    job["pdf_pages"] = pages
    _save_job(job_id, job)
    background_tasks.add_task(_run_job, job_id)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


def _extract_pdf_text(contents: bytes) -> str:
    pages = _extract_pdf_pages(contents)
    return "\n".join(page["text"] for page in pages).strip()


def _extract_pdf_pages(contents: bytes) -> list[dict[str, Any]]:
    reader = PdfReader(io.BytesIO(contents))
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        pages.append({"page_number": index, "text": page_text})
    return pages


def _build_keyword_evidence_from_pages(
    keywords: list[str],
    pages: list[dict[str, Any]],
    max_sources: int = 3,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for keyword in keywords:
        sources: list[dict[str, Any]] = []
        for page in pages:
            text = page.get("text", "")
            if not text:
                continue
            start = 0
            while True:
                pos = text.find(keyword, start)
                if pos == -1:
                    break
                sentence = _extract_sentence(text, pos)
                sources.append(
                    {
                        "page_number": page.get("page_number", 0),
                        "start_offset": pos,
                        "end_offset": pos + len(keyword),
                        "text": sentence,
                    }
                )
                if len(sources) >= max_sources:
                    break
                start = pos + len(keyword)
            if len(sources) >= max_sources:
                break
        evidence.append({"keyword": keyword, "sources": sources})
    return evidence


def _extract_sentence(text: str, pos: int) -> str:
    if not text:
        return ""
    left = max(text.rfind(".", 0, pos), text.rfind("!", 0, pos), text.rfind("?", 0, pos), text.rfind("\n", 0, pos))
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


@app.post("/flow/blueprint/upload")
async def generate_blueprint_upload(
    file: UploadFile = File(...),
    length_seconds: int = Form(...),
    mood: str = Form(...),
    genre: str = Form(...),
    llm_model: str = Form(...),
    llm_temperature: float = Form(...),
    hitl_mode: str = Form("skip"),
) -> dict[str, Any]:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF only")
    contents = await file.read()
    text = _extract_pdf_text(contents)
    if not text:
        raise HTTPException(status_code=400, detail="PDF text extraction failed")
    config = FlowConfig(
        genre=genre,
        mood=mood,
        length_seconds=length_seconds,
        llm_model=llm_model,
        llm_temperature=llm_temperature,
        hitl_mode=hitl_mode,
    )
    payload = BlueprintRequest(document=text, config=config)
    return generate_blueprint(payload)


class HitlRequest(BaseModel):
    job_id: str = Field(min_length=1)
    selected_concept_id: str = Field(min_length=1)
    edited_lyrics: str | None = None
    edited_mv_script: list[MVScriptScene] | None = None


@app.post("/flow/hitl")
def submit_hitl(payload: HitlRequest) -> dict[str, Any]:
    return submit_hitl_job(payload.job_id, payload)


@app.post("/jobs/{job_id}/hitl")
def submit_hitl_job(job_id: str, payload: HitlRequest) -> dict[str, Any]:
    if job_id != payload.job_id:
        raise HTTPException(status_code=400, detail="job_id mismatch")
    job = _load_job(payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    result = job.get("result", {})
    artifacts = result.get("job", {}).get("artifacts", {})
    concepts = [MVConcept.model_validate(item) for item in artifacts.get("concepts", [])]
    selected = next((c for c in concepts if c.concept_id == payload.selected_concept_id), None)
    if not selected:
        raise HTTPException(status_code=400, detail="selected_concept_id not found")

    if payload.edited_lyrics is not None:
        selected.lyrics = payload.edited_lyrics
    if payload.edited_mv_script is not None:
        selected.mv_script = payload.edited_mv_script

    qa_results = [QAResult.model_validate(item) for item in artifacts.get("qa_results", [])]
    keyword_summary = KeywordExtraction.model_validate(
        {
            "keywords": artifacts.get("extracted_keywords", []),
            "key_points": artifacts.get("key_points", []),
            "keyword_evidence": artifacts.get("keyword_evidence", []),
        }
    )
    response = _get_agentic_flow().continue_from_hitl(
        job_id=payload.job_id,
        document=job.get("payload", {}).get("document", ""),
        config=FlowConfig.model_validate(job.get("payload", {}).get("config", {})),
        selected_concept=selected,
        concepts=concepts,
        qa_results=qa_results,
        retry_count=result.get("job", {}).get("retry_count", 0),
        state_history=result.get("state_history", []),
        trace=result.get("trace", []),
        hitl_payload={
            "requires_human": False,
            "selected_concept_id": payload.selected_concept_id,
        },
        keyword_summary=keyword_summary,
    )
    artifacts = response.get("job", {}).get("artifacts", {})
    keywords = artifacts.get("extracted_keywords", [])
    pages = job.get("pdf_pages") or [{"page_number": 0, "text": job.get("payload", {}).get("document", "")}]
    artifacts["keyword_evidence"] = _build_keyword_evidence_from_pages(keywords, pages)
    if "job" in response:
        response["job"]["artifacts"] = artifacts
    _update_job(payload.job_id, status="completed", progress=1.0, result=response)
    return response