# 전략: 오디오-우선 + 오버랩 (hybrid_overlap)

## 한줄 요약
음악을 먼저 확정하고, 클립 간 오버랩을 이용해 자연스럽게 컷한다.

## 언제 쓰나
- 병렬 속도를 유지하면서 전환 품질도 챙기고 싶을 때

## 입력/출력
- 입력: safety_text, options, reference_audio(optional)
- 출력: 15초 클립 N개 + 최종 합성 mp4

### 입력 JSON 예시
```json
{
  "safety_text": "후진 시 경고음을 울린다...",
  "strategy": "hybrid_overlap",
  "options": {"duration_seconds": 60, "mood": "tense"},
  "attachments": {"reference_audio": ["minio://refs/beat.wav"]}
}
```

## 입력 스키마 (JSON Schema)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["safety_text", "strategy", "options"],
  "additionalProperties": false,
  "properties": {
    "safety_text": { "type": "string", "minLength": 1 },
    "strategy": { "type": "string", "enum": ["hybrid_overlap"] },
    "options": {
      "type": "object",
      "required": ["duration_seconds"],
      "additionalProperties": false,
      "properties": {
        "duration_seconds": { "type": "integer", "minimum": 30, "maximum": 90 },
        "mood": { "type": ["string", "null"] },
        "site_type": { "type": ["string", "null"] }
      }
    },
    "attachments": {
      "type": ["object", "null"],
      "additionalProperties": false,
      "properties": {
        "reference_images": { "type": "array", "items": { "type": "string" } },
        "reference_videos": { "type": "array", "items": { "type": "string" } },
        "reference_audio": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

### 출력 메타 예시
```json
{
  "clips": ["minio://jobs/<job_id>/clip_01.mp4"],
  "music": "minio://jobs/<job_id>/track_full.mp3",
  "final": "minio://jobs/<job_id>/final.mp4"
}
```

## 출력 스키마 (JSON Schema)
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["clips", "music", "final"],
  "additionalProperties": false,
  "properties": {
    "clips": { "type": "array", "items": { "type": "string" } },
    "music": { "type": "string" },
    "final": { "type": "string" }
  }
}
```

## 처리 단계 (상세)
1) 음악 생성 → 비트 맵 추출
2) 씬 플래너 (비트 맵 기준 타임코드)
3) 스타일 락 생성
4) **오버랩 포함 프롬프트** 생성 (15초 + 1~2초)
5) Sora 병렬 생성
6) 오버랩 트리밍 (비트에 맞춰 컷)
7) 렌더 합성

## A/V 싱크 전략
- **오디오가 절대 기준**.
- 컷 타임은 비트 맵 timecode에 고정.

## Sora 15초 제한 대응
- 모델 입력은 15초(또는 15초 + 오버랩)으로 고정, 렌더에서 길이 보정.

## 실패/재시도 정책
- 클립 단위 재시도
- 오디오 실패 시 오디오만 재생성

## 에러/재시도 규칙표
| 단계 | 실패 조건 | 재시도 | 폴백 |
| --- | --- | --- | --- |
| 비트 맵 | timecode 불일치 | 1회 | 고정 BPM + 균등 분할 |
| 클립 생성 | 길이/오버랩 오류 | 1회 | 오버랩 제거 후 재생성 |
| 오버랩 트리밍 | 컷 손상 | 1회 | 크로스페이드로 대체 |
| 음악 생성 | 실패/지연 | 1회 | 레퍼런스 오디오 사용 |

## LLM 프롬프트 템플릿
### 비트 맵 설계
```text
역할: 비트 맵 디자이너
목표: 60초 타임코드 설계
출력: beat_map (BPM, intro/verse/drop/outro)

mood:
{MOOD}
duration_seconds:
{DURATION_SECONDS}
```

### 오버랩 클립 프롬프트
```text
역할: Sora 프롬프트 작성기
목표: 오버랩을 포함한 클립 프롬프트 생성
출력: clip_prompt
제약: 시작/끝 1~2초는 전환에 유리한 움직임으로 설계

scene:
{SCENE_JSON}
style_lock:
{STYLE_LOCK}
beat_map:
{BEAT_MAP}
```

## 다이어그램
```mermaid
flowchart TD
  A[Input] --> B[Music Gen]
  B --> C[Beat Map]
  C --> D[Scene Planner]
  D --> E[Style Lock]
  D --> F[Prompt Builder (overlap)]
  E --> F
  F --> G1[Sora clip 1]
  F --> G2[Sora clip 2]
  F --> G3[Sora clip 3]
  G1 --> H[Overlap Trim]
  G2 --> H
  G3 --> H
  H --> I[Render]
  B --> I
  I --> J[Result]
```
