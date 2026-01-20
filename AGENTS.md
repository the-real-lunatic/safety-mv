# AGENTS.md

## Repo 목적
SafetyMV 인프라 스캐폴딩. (frontend + backend + MinIO + Redis)
안전 수칙 문서를 입력하면 30~90초 “뮤직비디오형” 안전 영상을 생성한다는 컨셉을 바탕으로, **파이프라인 구현 없이** 인프라/스캐폴딩과 전략 문서만 정리한다.

## 서비스 구성
- `frontend/`: 정적 Welcome 페이지 (Vite)
- `backend/`: FastAPI 헬스 체크 API + 공통 Job API (스캐폴딩)
- `docker-compose.yml`: 전체 스택 실행
- `strategies/`: 전략별 문서(한글) + 프롬프트 템플릿 + 다이어그램

## 실행 방법
- 개발/테스트: `docker compose up --build`
- Frontend: http://localhost:3000
- Backend Swagger: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

## 헬스 체크 API
- `GET /health`
- `GET /health/redis`
- `GET /health/minio`
 - `GET /health/openai` (OPENAI_API_KEY + OPENAI_HEALTHCHECK_MODEL 필요)
 - `GET /health/sora` (SORA_API_KEY 필요, /v1/videos 호출)
 - `GET /health/suno` (SUNO_API_KEY 필요, 크레딧 조회)

## 공통 Job API (스캐폴딩)
- `GET /strategies`
- `POST /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`

## 작업 원칙
- 이번 단계에서는 파이프라인/모델 로직 구현 금지.
- 인프라 및 기본 스캐폴딩만 유지.
- 신규 기능은 서비스 분리 구조를 유지하며 추가.
- 전략별 구현은 문서/스캐폴딩만 작성하고, 실제 생성 호출은 넣지 않는다.

## 컨텍스트 빠른 복구 (Codex용)
- 기획 배경: `safety-mv-concept.md`
- 전략 목록/설명: `strategies/README.md`
- 전략별 상세/프롬프트/다이어그램: `strategies/<strategy_id>.md`
- 공통 백엔드 스캐폴딩: `backend/app/core/` + `backend/app/api/routes/jobs.py`
- 전략 자동 로딩: `backend/app/core/strategy_loader.py` (strategies 폴더의 `.md` 파일명 사용)
- 렌더/오디오/비디오 실제 파이프라인은 아직 미구현
 - Sora 제약: 15초 클립만 생성 가능 → 다중 클립 합성 필요
 - A/V 싱크: 비트맵(timecode) 기반으로 컷과 오디오를 정렬하는 전략 필요

## 로컬 실행 요약
- `docker compose up --build`
- 전략 목록: `GET http://localhost:8000/strategies`
- 헬스체크: `/health`, `/health/redis`, `/health/minio`

## 환경 변수
- `.env.example` 참고
- `STRATEGY_DIR=/app/strategies` 기본 (docker-compose에서 strategies 마운트)
 - `OPENAI_API_BASE_URL=https://api.openai.com/v1`
 - `SORA_API_BASE_URL=https://api.openai.com/v1`
 - `SUNO_API_BASE_URL=https://api.sunoapi.org`

## 전략 파일 규칙
- `strategies/` 하위의 **`.md` 파일명**이 strategy_id
- `strategies/README.md`는 설명용이며 API 목록에 포함되지 않음

## 핵심 제약 요약
- 파이프라인/모델 실제 호출 금지 (스캐폴딩/문서만)
- 전략은 서로 다른 구현 방향을 문서로 제시
- 병렬/순차 처리, 앵커, 오버랩, 비디오 체인 등 아이디어만 정리
