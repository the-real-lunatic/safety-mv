# Integrated Request/Response (Polling)

프론트는 **`GET /jobs/{job_id}` 하나만 polling**한다.

---

## GET /jobs/{job_id}

### Response Example (HITL required)
```json
{
  "job_id": "job_ab12cd",
  "status": "hitl_required",
  "progress": 0.8,
  "result": {
    "concepts": [
      { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] },
      { "concept_id": "c2", "lyrics": "...", "mv_script": [{ "start": 0, "end": 6, "description": "..." }] }
    ],
    "qa_results": [
      { "result": "pass", "score": 0.82, "missing_keywords": [], "structural_issues": [] },
      { "result": "pass", "score": 0.74, "missing_keywords": [], "structural_issues": [] }
    ],
    "selected_concept": { "concept_id": "c1", "lyrics": "...", "mv_script": [{ "start": 0, "end": 5, "description": "..." }] }
  },
  "error": null
}
```

### Response Example (media_running)
```json
{
  "job_id": "job_ab12cd",
  "status": "media_running",
  "progress": 0.85,
  "result": {
    "selected_concept": { "concept_id": "c1" },
    "blueprint": { "duration": 60, "scenes": ["..."] },
    "style": { "character": "...", "background": "...", "color": "..." },
    "character_asset": { "asset_id": "asset_xyz", "status": "ready" },
    "video_jobs": [
      { "scene_id": "scene_1", "status": "stored", "video_id": "video_123" },
      { "scene_id": "scene_2", "status": "queued", "video_id": "video_456" }
    ],
    "suno": { "status": "queued", "task_id": "task_abc" }
  },
  "error": null
}
```

### Response Example (media_done)
```json
{
  "job_id": "job_ab12cd",
  "status": "media_done",
  "progress": 1.0,
  "result": {
    "selected_concept": { "concept_id": "c1" },
    "blueprint": { "duration": 60, "scenes": ["..."] },
    "style": { "character": "...", "background": "...", "color": "..." },
    "character_asset": { "asset_id": "asset_xyz", "status": "ready" },
    "video_jobs": [
      { "scene_id": "scene_1", "status": "stored", "video_id": "video_123" },
      { "scene_id": "scene_2", "status": "stored", "video_id": "video_456" }
    ],
    "suno": { "status": "stored", "task_id": "task_abc" },
    "output_url": "https://minio.../outputs/job_ab12cd/final.mp4"
  },
  "error": null
}
```
