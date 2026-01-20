# Integrated Request/Response (SafetyMV)

## 1) POST /jobs

### Request
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
- file: PDF
- guidelines: string (optional)
- length: string ("30s" | "60s" | "90s")
- selectedStyles: string (comma separated)
- selectedGenres: string
- additionalRequirements: string
- llm_model: string
- llm_temperature: number
- hitl_mode: string

### Response
```json
{
  "job_id": "job_ab12cd"
}
```

---

## 3) GET /jobs/{job_id}

### Response (processing)
```json
{
  "job_id": "job_ab12cd",
  "status": "running",
  "progress": 0.3,
  "result": null,
  "error": null
}
```

### Response (HITL required)
```json
{
  "job_id": "job_ab12cd",
  "status": "hitl_required",
  "progress": 0.8,
  "result": {
    "job": {
      "state": "HITL",
      "artifacts": {
        "extracted_keywords": ["..."],
        "key_points": ["..."],
        "keyword_evidence": [
          {
            "keyword": "장비",
            "sources": [
              { "page_number": 2, "start_offset": 15, "end_offset": 17, "text": "장비 이상 징후 발견 시 즉시 중지한다." }
            ]
          }
        ]
      }
    },
    "hitl": { "requires_human": true, "selected_concept_id": "c1" },
    "state_history": ["INIT", "CONCEPT_GEN", "QA", "HITL"],
    "trace": ["..."]
  },
  "error": null
}
```

### Response (completed)
```json
{
  "job_id": "job_ab12cd",
  "status": "completed",
  "progress": 1.0,
  "result": {
    "job": {
      "state": "STYLE_BIND",
      "artifacts": {
        "extracted_keywords": ["..."],
        "key_points": ["..."],
        "keyword_evidence": [
          {
            "keyword": "보호구",
            "sources": [
              { "page_number": 1, "start_offset": 8, "end_offset": 11, "text": "작업 전 보호구를 착용한다." }
            ]
          }
        ],
        "character_asset": {
          "provider": "sora",
          "asset_id": "asset_xyz",
          "status": "submitted",
          "prompt": "..."
        },
        "media_plan": {
          "character_asset_id": "asset_xyz",
          "character_job": {
            "job_id": "character_ref",
            "provider": "sora",
            "api_key_env": "SORA_API_KEY",
            "type": "image",
            "prompt": "...",
            "asset_id": "asset_xyz",
            "status": "submitted"
          },
          "video_jobs": [
            {
              "scene_id": "scene_1",
              "provider": "sora",
              "api_key_env": "SORA_API_KEY",
              "type": "video",
              "duration_seconds": 8,
              "prompt": "...",
              "character_reference": "character_ref",
              "character_asset_id": "asset_xyz"
            }
          ],
          "music_job": {
            "provider": "suno",
            "api_key_env": "SUNO_API_KEY",
            "prompt": "..."
          }
        }
      }
    },
    "hitl": { "requires_human": false },
    "state_history": ["INIT", "CONCEPT_GEN", "QA", "LOCK_BLUEPRINT_CORE", "STYLE_BIND"],
    "trace": ["..."]
  },
  "error": null
}
```

### keyword_evidence 설명
- page_number: PDF 기준 1부터, 사용자 입력만 있으면 0
- start_offset / end_offset: 해당 페이지 텍스트 기준의 위치

---

## 4) POST /jobs/{job_id}/hitl

### Request
```json
{
  "job_id": "job_ab12cd",
  "selected_concept_id": "c1",
  "edited_lyrics": "(optional)",
  "edited_mv_script": [
    {"start": 0, "end": 5, "description": "..."}
  ]
}
```

---

## 5) GET /jobs/{job_id}/character

### Response
```json
{
  "asset_id": "asset_xyz",
  "status": "ready",
  "preview_url": "https://...signed..."
}
```

---

## 6) GET /jobs/{job_id}/character/image

### Response
- 이미지 바이너리 (content-type: image/*)

### Response
```json
{
  "job": { "state": "STYLE_BIND" },
  "hitl": { "requires_human": false },
  "state_history": ["..."],
  "trace": ["..."]
}
```
