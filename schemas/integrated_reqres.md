# Integrated Request/Response (SafetyMV)

아래 예시는 `schemas/integrated_reqres.json`의 예시 구조를 그대로 반영한다.

---

## 1) POST /jobs

### Request (application/json)
```json
{
  "guidelines": "안전 텍스트...",
  "length": "30s",
  "selectedStyles": ["minimal", "modern"],
  "selectedGenres": "hiphop",
  "additionalRequirements": "",
  "llm_model": "gpt-4o-mini",
  "llm_temperature": 0.4,
  "hitl_mode": "skip"
}
```

### Response
```json
{
  "job_id": "job_ab12cd"
}
```

---

## 2) POST /jobs/upload

### Request (multipart/form-data)
- file: PDF file
- guidelines: string (optional)
- length: "30s" | "60s" | "90s"
- selectedStyles: comma-separated string
- selectedGenres: string
- additionalRequirements: string
- llm_model: string
- llm_temperature: number
- hitl_mode: "skip" | "required"

### Response
```json
{
  "job_id": "job_ab12cd"
}
```

---

## 3) GET /jobs/{job_id}

### Response (schema)
```json
{
  "job_id": "string",
  "status": "queued | running | completed | hitl_required | failed",
  "progress": "number",
  "result": {
    "job": {
      "job_id": "string",
      "state": "string",
      "retry_count": "number",
      "artifacts": "object"
    },
    "hitl": "object",
    "state_history": ["string"],
    "trace": ["object"]
  },
  "error": "string | null"
}
```

### Response Example (hitl_required)
```json
{
  "job_id": "job_ab12cd",
  "status": "hitl_required",
  "progress": 0.8,
  "result": {
    "job": {
      "state": "HITL",
      "retry_count": 0,
      "artifacts": {
        "extracted_keywords": ["..."],
        "key_points": ["..."],
        "keyword_evidence": [
          {
            "keyword": "장비",
            "sources": [
              { "page_number": 2, "start_offset": 15, "end_offset": 17, "text": "..." }
            ]
          }
        ],
        "concepts": [
          { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] },
          { "concept_id": "c2", "lyrics": "...", "mv_script": [{ "start": 0, "end": 6, "description": "..." }] }
        ],
        "qa_results": [
          { "result": "pass", "score": 0.82, "missing_keywords": [], "structural_issues": [] },
          { "result": "pass", "score": 0.74, "missing_keywords": [], "structural_issues": [] }
        ],
        "selected_concept": { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] }
      }
    },
    "hitl": { "requires_human": true, "selected_concept_id": "c1" },
    "state_history": ["INIT", "CONCEPT_GEN", "QA", "HITL"],
    "trace": ["..."]
  },
  "error": null
}
```

### Response Example (completed)
```json
{
  "job_id": "job_ab12cd",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "job": {
      "state": "STYLE_BIND",
      "artifacts": {
        "selected_concept": { "concept_id": "c1" },
        "blueprint": { "duration": 60, "scenes": ["..."] },
        "style": { "character": "...", "background": "...", "color": "..." },
        "media_plan": { "character_job": "...", "video_jobs": ["..."], "music_job": "..." },
        "character_asset": { "asset_id": "asset_xyz", "status": "ready" }
      }
    },
    "hitl": { "requires_human": false },
    "state_history": ["..."],
    "trace": ["..."]
  },
  "error": null
}
```

### Response Examples (as response_examples block)
```json
{
  "response_examples": {
    "hitl_required": {
      "job_id": "job_ab12cd",
      "status": "hitl_required",
      "progress": 0.8,
      "result": {
        "job": {
          "state": "HITL",
          "retry_count": 0,
          "artifacts": {
            "extracted_keywords": ["..."],
            "key_points": ["..."],
            "keyword_evidence": [
              {
                "keyword": "장비",
                "sources": [
                  { "page_number": 2, "start_offset": 15, "end_offset": 17, "text": "..." }
                ]
              }
            ],
            "concepts": [
              { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] },
              { "concept_id": "c2", "lyrics": "...", "mv_script": [{ "start": 0, "end": 6, "description": "..." }] }
            ],
            "qa_results": [
              { "result": "pass", "score": 0.82, "missing_keywords": [], "structural_issues": [] },
              { "result": "pass", "score": 0.74, "missing_keywords": [], "structural_issues": [] }
            ],
            "selected_concept": { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] }
          }
        },
        "hitl": { "requires_human": true, "selected_concept_id": "c1" },
        "state_history": ["INIT", "CONCEPT_GEN", "QA", "HITL"],
        "trace": ["..."]
      },
      "error": null
    },
    "completed": {
      "job_id": "job_ab12cd",
      "status": "completed",
      "progress": 1.0,
      "result": {
        "job": {
          "state": "STYLE_BIND",
          "artifacts": {
            "selected_concept": { "concept_id": "c1" },
            "blueprint": { "duration": 60, "scenes": ["..."] },
            "style": { "character": "...", "background": "...", "color": "..." },
            "media_plan": { "character_job": "...", "video_jobs": ["..."], "music_job": "..." },
            "character_asset": { "asset_id": "asset_xyz", "status": "ready" }
          }
        },
        "hitl": { "requires_human": false },
        "state_history": ["..."],
        "trace": ["..."]
      },
      "error": null
    }
  }
}
```

---

## 4) POST /jobs/{job_id}/hitl

### Request
```json
{
  "job_id": "job_ab12cd",
  "selected_concept_id": "c1"
}
```

### Response Example
```json
{
  "job": {
    "state": "STYLE_BIND",
    "artifacts": {
      "selected_concept": { "concept_id": "c1" },
      "blueprint": { "duration": 60, "scenes": ["..."] },
      "style": { "character": "...", "background": "...", "color": "..." },
      "media_plan": { "character_job": "...", "video_jobs": ["..."], "music_job": "..." },
      "character_asset": { "asset_id": "asset_xyz", "status": "ready" }
    }
  },
  "hitl": { "requires_human": false },
  "state_history": ["string"],
  "trace": ["object"]
}
```

---

## 5) GET /jobs/{job_id}/character

### Response
```json
{
  "asset_id": "string",
  "status": "string",
  "preview_url": "string | null"
}
```

---

## 6) GET /jobs/{job_id}/character/image

### Response
- image/* binary
