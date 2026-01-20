from __future__ import annotations

import json
import os
import time
import tempfile
import subprocess
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import io
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import base64
import httpx
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
from .suno_integration import attach_public_suno, trigger_suno_for_job
from .suno_routes import router as suno_router
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
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(suno_router)

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


def _ensure_bucket(bucket: str) -> None:
    client = _get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def _presign_minio_object(bucket: str, key: str, expiry_seconds: int = 3600) -> str | None:
    client = _get_minio_client()
    try:
        return client.presigned_get_object(bucket, key, expires=expiry_seconds)
    except Exception:
        return None


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
        if status == "completed":
            trigger_suno_for_job(job_id, response)
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
        llm_model="gpt-4o-mini",
        llm_temperature=0.4,
        hitl_mode="required",
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
    result = job.get("result") or {}
    artifacts = result.get("job", {}).get("artifacts", {}) or {}
    status = job.get("status")
    public_result = None
    if status == "hitl_required":
        public_result = {
            "concepts": artifacts.get("concepts") or [],
            "qa_results": artifacts.get("qa_results") or [],
            "selected_concept": artifacts.get("selected_concept"),
        }
    elif status in {"completed", "media_running", "media_done"}:
        public_result = {
            "selected_concept": artifacts.get("selected_concept"),
            "blueprint": artifacts.get("blueprint"),
            "style": artifacts.get("style"),
            "media_plan": artifacts.get("media_plan"),
            "character_asset": artifacts.get("character_asset"),
            "video_jobs": artifacts.get("video_jobs"),
            "suno": job.get("suno"),
            "output_url": artifacts.get("output_url"),
        }
    response_payload = {
        "job_id": job.get("job_id", job_id),
        "status": status,
        "progress": job.get("progress"),
        "result": public_result,
        "error": job.get("error"),
    }
    return response_payload


@app.get("/jobs/{job_id}/debug")
def get_job_debug(job_id: str) -> dict[str, Any]:
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return attach_public_suno(job)


def _resolve_character_asset(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result", {}) or {}
    artifacts = result.get("job", {}).get("artifacts", {}) or {}
    asset = artifacts.get("character_asset", {}) or {}
    media_plan = artifacts.get("media_plan", {}) or {}
    asset_id = asset.get("asset_id") or media_plan.get("character_asset_id")
    return {"asset_id": asset_id, "asset": asset}


@app.get("/jobs/{job_id}/character")
def get_character_asset(job_id: str) -> dict[str, Any]:
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    resolved = _resolve_character_asset(job)
    asset_id = resolved.get("asset_id")
    if not asset_id:
        raise HTTPException(status_code=404, detail="character asset not found")
    asset = resolved.get("asset", {})
    if asset.get("preview_url"):
        return {
            "asset_id": asset_id,
            "status": asset.get("status"),
            "preview_url": asset.get("preview_url"),
        }
    sora_response = _get_agentic_flow().sora.get_asset(asset_id)
    preview_url = sora_response.get("url") or asset.get("preview_url")
    status = sora_response.get("status") or asset.get("status")
    payload = {
        "asset_id": asset_id,
        "status": status,
        "preview_url": preview_url,
    }
    if sora_response.get("detail"):
        payload["detail"] = sora_response["detail"]
    return payload


@app.get("/jobs/{job_id}/character/image")
def get_character_image(job_id: str) -> Response:
    job = _load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    resolved = _resolve_character_asset(job)
    asset_id = resolved.get("asset_id")
    if not asset_id:
        raise HTTPException(status_code=404, detail="character asset not found")
    asset = resolved.get("asset", {})
    if asset.get("preview_b64"):
        image = base64.b64decode(asset["preview_b64"])
        return Response(content=image, media_type="image/png")
    image, content_type = _get_agentic_flow().sora.fetch_image(asset_id)
    if not image:
        raise HTTPException(status_code=404, detail="character image not ready")
    return Response(content=image, media_type=content_type or "image/png")


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


def _normalize_video_seconds(duration: float) -> str:
    if duration <= 4:
        return "4"
    if duration <= 8:
        return "8"
    return "12"


def _build_style_base(style: dict[str, Any]) -> str:
    character = style.get("character", {}) if isinstance(style, dict) else {}
    background = style.get("background", {}) if isinstance(style, dict) else {}
    color = style.get("color", {}) if isinstance(style, dict) else {}
    return (
        f"character: {character.get('appearance', '')}, outfit: {character.get('outfit', '')}; "
        f"background: {background.get('environment', '')}, lighting: {background.get('lighting', '')}; "
        f"color: {color.get('primary', '')}/{color.get('secondary', '')}"
    )


def _get_character_image_bytes(asset: dict[str, Any]) -> bytes | None:
    if not asset:
        return None
    if asset.get("preview_b64"):
        try:
            return base64.b64decode(asset["preview_b64"])
        except Exception:  # noqa: BLE001
            return None
    preview_url = asset.get("preview_url")
    if isinstance(preview_url, str) and preview_url.startswith("data:image"):
        try:
            _, b64 = preview_url.split(",", 1)
            return base64.b64decode(b64)
        except Exception:  # noqa: BLE001
            return None
    if isinstance(preview_url, str) and preview_url.startswith("http"):
        try:
            response = httpx.get(preview_url, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception:  # noqa: BLE001
            return None
    return None


def _run_media_pipeline(job_id: str) -> None:
    job = _load_job(job_id)
    if not job:
        return
    result = job.get("result", {}) or {}
    artifacts = result.get("job", {}).get("artifacts", {}) or {}
    blueprint = artifacts.get("blueprint")
    style = artifacts.get("style")
    if not blueprint or not style:
        return
    character_asset = artifacts.get("character_asset", {}) or {}
    reference_bytes = _get_character_image_bytes(character_asset)
    if reference_bytes is None:
        artifacts["video_jobs"] = [
            {
                "scene_id": None,
                "status": "skipped",
                "detail": "character reference image missing",
            }
        ]
        if "job" in result:
            result["job"]["artifacts"] = artifacts
        _update_job(job_id, result=result)
        _mark_media_status(job_id)
        return
    base_style = _build_style_base(style)
    scenes = blueprint.get("scenes", [])
    max_workers = min(6, max(1, len(scenes)))
    video_jobs: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_process_scene_video, job_id, idx, scene, base_style, reference_bytes): scene
            for idx, scene in enumerate(scenes, start=1)
        }
        for future in as_completed(futures):
            video_jobs.append(future.result())
    artifacts["video_jobs"] = sorted(video_jobs, key=lambda item: item.get("scene_id") or "")
    if "job" in result:
        result["job"]["artifacts"] = artifacts
    _update_job(job_id, result=result)
    _mark_media_status(job_id)
    _try_finalize_render(job_id)


def _process_scene_video(
    job_id: str,
    index: int,
    scene: dict[str, Any],
    base_style: str,
    reference_bytes: bytes,
) -> dict[str, Any]:
    time_range = scene.get("time_range", {}) if isinstance(scene, dict) else {}
    duration = max(1.0, float(time_range.get("end", 0)) - float(time_range.get("start", 0)))
    seconds = _normalize_video_seconds(duration)
    prompt = (
        f"{base_style}. "
        f"visual action: {scene.get('visual', {}).get('action', '')}. "
        f"camera: {scene.get('visual', {}).get('camera', '')}. "
        f"lyrics: {scene.get('lyrics', {}).get('text', '')}."
    ).strip()
    sora = _get_agentic_flow().sora
    create_resp = sora.create_video(
        prompt=prompt,
        reference_image=reference_bytes,
        seconds=seconds,
    )
    video_id = create_resp.get("video_id")
    status = create_resp.get("status")
    detail = create_resp.get("detail")
    scene_id = scene.get("scene_id") or f"scene_{index:02d}"
    if not video_id or status == "error":
        return {
            "scene_id": scene_id,
            "prompt": prompt,
            "target_duration_seconds": duration,
            "requested_seconds": seconds,
            "status": status or "error",
            "video_id": video_id,
            "detail": detail,
        }

    timeout_seconds = int(os.getenv("SORA_VIDEO_TIMEOUT", "600"))
    poll_interval = float(os.getenv("SORA_VIDEO_POLL_INTERVAL", "5"))
    start = time.time()
    current_status = status
    while time.time() - start < timeout_seconds:
        poll = sora.retrieve_video(video_id)
        current_status = poll.get("status") or current_status
        if current_status in {"succeeded", "complete", "completed"}:
            break
        if current_status in {"failed", "error"}:
            return {
                "scene_id": scene_id,
                "prompt": prompt,
                "target_duration_seconds": duration,
                "requested_seconds": seconds,
                "status": current_status,
                "video_id": video_id,
                "detail": poll.get("detail"),
            }
        time.sleep(poll_interval)

    download = sora.download_video_content(video_id)
    if download.get("status") != "downloaded":
        return {
            "scene_id": scene_id,
            "prompt": prompt,
            "target_duration_seconds": duration,
            "requested_seconds": seconds,
            "status": "download_failed",
            "video_id": video_id,
            "detail": download.get("detail"),
        }

    bucket = os.getenv("MINIO_BUCKET_VIDEO", "safety-mv")
    _ensure_bucket(bucket)
    key = f"videos/{job_id}/scene_{index:02d}.mp4"
    content = download["content"]
    client = _get_minio_client()
    client.put_object(
        bucket,
        key,
        io.BytesIO(content),
        length=len(content),
        content_type=download.get("content_type") or "video/mp4",
    )
    return {
        "scene_id": scene_id,
        "prompt": prompt,
        "target_duration_seconds": duration,
        "requested_seconds": seconds,
        "status": "stored",
        "video_id": video_id,
        "minio_bucket": bucket,
        "minio_key": key,
        "minio_url": _presign_minio_object(bucket, key),
    }


def _try_finalize_render(job_id: str) -> None:
    job = _load_job(job_id)
    if not job:
        return
    result = job.get("result", {}) or {}
    artifacts = result.get("job", {}).get("artifacts", {}) or {}
    video_jobs = artifacts.get("video_jobs") or []
    if not video_jobs:
        return
    if any(vjob.get("status") != "stored" for vjob in video_jobs):
        return
    suno = job.get("suno") or {}
    tracks = suno.get("tracks") or []
    if not tracks:
        return
    audio_track = tracks[0]
    audio_bucket = audio_track.get("minio_bucket") or os.getenv("MINIO_BUCKET_MUSIC", "safety-mv")
    audio_key = audio_track.get("minio_audio_key")
    if not audio_key:
        return

    client = _get_minio_client()
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            video_paths = []
            for idx, vjob in enumerate(sorted(video_jobs, key=lambda item: item.get("minio_key", "")), start=1):
                bucket = vjob.get("minio_bucket") or os.getenv("MINIO_BUCKET_VIDEO", "safety-mv")
                key = vjob.get("minio_key")
                if not key:
                    return
                local_path = os.path.join(tmpdir, f"scene_{idx:02d}.mp4")
                client.fget_object(bucket, key, local_path)
                video_paths.append(local_path)

            audio_path = os.path.join(tmpdir, "music.mp3")
            client.fget_object(audio_bucket, audio_key, audio_path)

            list_path = os.path.join(tmpdir, "concat.txt")
            with open(list_path, "w", encoding="utf-8") as handle:
                for path in video_paths:
                    handle.write(f"file '{path}'\n")

            concat_path = os.path.join(tmpdir, "concat.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", concat_path],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            output_path = os.path.join(tmpdir, "final.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    concat_path,
                    "-i",
                    audio_path,
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-shortest",
                    output_path,
                ],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            output_bucket = os.getenv("MINIO_BUCKET_OUTPUT", "safety-mv")
            _ensure_bucket(output_bucket)
            output_key = f"outputs/{job_id}/final.mp4"
            client.fput_object(output_bucket, output_key, output_path, content_type="video/mp4")
            artifacts["output_url"] = _presign_minio_object(output_bucket, output_key)
            artifacts["output_key"] = output_key
            artifacts["output_bucket"] = output_bucket
            if "job" in result:
                result["job"]["artifacts"] = artifacts
            _update_job(job_id, result=result, status="media_done", progress=1.0)
    except Exception as exc:  # noqa: BLE001
        _update_job(job_id, error=str(exc))


def _mark_media_status(job_id: str) -> None:
    job = _load_job(job_id)
    if not job:
        return
    if job.get("status") == "media_done":
        return
    result = job.get("result", {}) or {}
    artifacts = result.get("job", {}).get("artifacts", {}) or {}
    video_jobs = artifacts.get("video_jobs") or []
    suno_status = (job.get("suno") or {}).get("status")
    suno_done = suno_status in {"stored", "complete"}
    if not suno_status:
        suno_done = True
    video_done = False
    if video_jobs:
        video_done = True
        for video in video_jobs:
            status = video.get("status")
            if status in {"error", "failed"}:
                video_done = False
                break
    if video_done and suno_done and artifacts.get("output_url"):
        _update_job(job_id, status="media_done", progress=1.0)
    else:
        _update_job(job_id, status="media_running", progress=0.85)


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


class CharacterImageRequest(BaseModel):
    prompt: str = Field(default="SafetyMV character reference, full body, front view.")


@app.post("/flow/hitl")
def submit_hitl(payload: HitlRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    return submit_hitl_job(payload.job_id, payload, background_tasks)


@app.post("/jobs/{job_id}/hitl")
def submit_hitl_job(job_id: str, payload: HitlRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
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
    _update_job(payload.job_id, status="media_running", progress=0.65, result=response)
    background_tasks.add_task(_run_media_pipeline, payload.job_id)
    background_tasks.add_task(trigger_suno_for_job, payload.job_id, response)
    return response


@app.post("/debug/character-image")
def debug_character_image(payload: CharacterImageRequest) -> dict[str, Any]:
    sora = _get_agentic_flow().sora
    response = sora.create_image(payload.prompt)
    preview_url = None
    if response.get("b64_json"):
        preview_url = f"data:image/png;base64,{response['b64_json']}"
    elif isinstance(response.get("response"), dict):
        preview_url = sora._extract_asset_url(response.get("response"))  # type: ignore[attr-defined]
    return {
        "status": response.get("status"),
        "asset_id": response.get("asset_id"),
        "preview_url": preview_url,
        "detail": response.get("detail"),
    }
