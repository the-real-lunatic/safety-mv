# AGENTS.md

## Repo 목적
SafetyMV 인프라 스캐폴딩. (frontend + backend + MinIO + Redis)

## 서비스 구성
- `frontend/`: 정적 Welcome 페이지 (Vite)
- `backend/`: FastAPI 헬스 체크 API
- `docker-compose.yml`: 전체 스택 실행

## 실행 방법
- 개발/테스트: `docker compose up --build`
- Frontend: http://localhost:3000
- Backend Swagger: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

## 헬스 체크 API
- `GET /health`
- `GET /health/redis`
- `GET /health/minio`

## 작업 원칙
- 이번 단계에서는 파이프라인/모델 로직 구현 금지.
- 인프라 및 기본 스캐폴딩만 유지.
- 신규 기능은 서비스 분리 구조를 유지하며 추가.
