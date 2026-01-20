# Safety MV AI — Multi-Agent Constitution

본 문서는 Safety MV AI 시스템에서 사용되는 모든 에이전트의
역할, 책임, 권한, 그리고 상호작용 규칙을 정의한다.

이 시스템은 "한 번에 잘 만들기"가 아니라
"실패를 전제로, 검증과 인간 개입을 통해
신뢰 가능한 MV 결과물을 만드는 것"을 목표로 한다.

---

## Global Principles

1. 모든 생성(Generation)은 실패할 수 있다.
2. 검증(Validation)은 반드시 수행된다.
3. 최종 창작 결정은 인간(Human-in-the-loop)이 승인한다.
4. 실패는 국소적으로 격리되며 전체 파이프라인을 재실행하지 않는다.
5. 잠긴 산출물은 이후 어떤 에이전트도 수정할 수 없다.
6. 모든 에이전트는 자신의 역할 범위를 넘는 판단을 하지 않는다.

---

## Agent Overview

| Agent | 핵심 산출물 | 생성 권한 | 결정 권한 |
|------|------------|----------|----------|
| Orchestrator | 상태 전이 / 잠금 | ❌ | ✅ |
| ConceptGen | 가사 + MV 컨셉 초안 | ✅ | ❌ |
| QA_Scorer | 검증 결과 | ❌ | ✅ |
| HITL_Pick | 인간 선택 결과 | ✏️ | ✅ |
| BlueprintAssembler | MV Blueprint | ❌ | ❌ |
| StyleBinder | 캐릭터/배경 메타데이터 | ❌ | ❌ |
| MediaWorkers | 미디어 결과물 | ❌ | ❌ |
| Renderer | 최종 영상 | ❌ | ❌ |

---

## Agent: Orchestrator

### 역할
- 전체 파이프라인의 상태 머신을 관리한다
- 어떤 에이전트를 언제 호출할지 결정한다
- 재시도, 중단, 잠금 조건을 판단한다

### 할 수 없는 것
- 콘텐츠(가사, 연출, 음악, 영상)를 직접 생성하지 않는다
- 하위 에이전트의 출력을 수정하지 않는다

### 불변 규칙
- 동일 상태는 두 번 실행되지 않는다
- 잠긴 산출물은 다시 열리지 않는다
- 모든 상태 전이는 로그로 기록된다

### 입력
- user_inputs (genre, vibe, duration 등)

### 출력
- job_id
- 최종 artifact 경로

---

## Agent: ConceptGen

### 역할
- 사용자 입력을 기반으로
  **가사 + MV 연출 초안이 포함된 컨셉 후보 2개를 생성한다**

### 규칙
- 정확성 보장을 시도하지 않는다
- 반드시 2개의 후보만 생성한다
- 캐릭터/배경을 고정하지 않는다 (암시만 허용)

### 출력
- concept_candidates[2]

---

## Agent: QA_Scorer

### 역할
- 컨셉 후보가 필수 안전/구조 요건을 충족하는지 검증한다

### 규칙
- 명시되지 않은 규칙은 누락으로 판단한다
- 창의성, 감성 품질은 평가하지 않는다

### 출력
- pass / fail
- missing_keywords
- structural_issues
- score (0.0 ~ 1.0)

---

## Agent: HITL_Pick

### 역할
- 인간 사용자가 컨셉을 선택하거나 수정한다
- 최종 창작 책임을 인간에게 귀속시킨다

### 출력
- selected_concept_id
- edited_lyrics (optional)
- edited_mv_script (optional)

---

## Agent: BlueprintAssembler

### 역할
- 선택된 컨셉을 **정규화된 MV Blueprint**로 변환한다

### 규칙
- 창의적 판단을 하지 않는다
- 구조적 정합성만 보장한다

---

## Agent: StyleBinder

### 역할
- MV 전반에 사용될 **불변 메타데이터**를 고정한다
- 캐릭터, 배경, 색감, 톤 규칙을 정의한다

### 규칙
- Blueprint 이후 스타일은 변경 불가

---

## Agent: MediaWorkers

### 역할
- 주어진 Blueprint와 스타일 메타데이터를 그대로 실행한다
- 판단이나 수정은 하지 않는다

구성:
- SunoMusic
- SoraVideo

---

## Agent: Renderer

### 역할
- 생성된 미디어들을 병합하여 최종 MV를 만든다

blueprint schema
MV BLUEPRINT
│
├── duration: 60s
│
├── scene[0]
│   ├── time: 0s ───────── 8s
│   ├── lyrics:
│   │   └── "첫 문장 가사"
│   ├── visual:
│   │   ├── action: 캐릭터 등장
│   │   └── camera: slow zoom in
│   └── audio:
│       └── music_section: intro
│
├── scene[1]
│   ├── time: 8s ───────── 20s
│   ├── lyrics:
│   │   └── "후렴 전 가사"
│   ├── visual:
│   │   ├── action: 걷기
│   │   └── camera: tracking shot
│   └── audio:
│       └── music_section: verse
│
├── scene[2]
│   ├── time: 20s ──────── 40s
│   ├── lyrics:
│   │   └── "후렴"
│   ├── visual:
│   │   ├── action: 점프
│   │   └── camera: wide shot
│   └── audio:
│       └── music_section: chorus
│
└── scene[3]
    ├── time: 40s ──────── 60s
    ├── lyrics:
    │   └── "엔딩 가사"
    ├── visual:
    │   ├── action: 퇴장
    │   └── camera: fade out
    └── audio:
        └── music_section: outro

- home
    
    input
    
    - 안전 텍스트
    - 영상 바이브 (택2)
        - minimal
        - corporated
        - modern
        - cute
    - 음악 장르 (택 1)
        - 힙합
        - 재즈
        - 트로트
        - 알앤비
        - 발라드
        - 락
        - 댄스
        - 케이팝
    - 추가 요구사항 텍스트
- lyrics_selection
    
    시안 버전 2개
    
    둘 중 하나 선택
    
- 생성 중 화면 왕 길게 나올듯
    
    
- 완성본 보여주는 화면
    
    다운로드?
    

- **polling**
    
    ## 전체 흐름 (한 줄 요약)
    
    **post_job → (가사 생성) → lyrics_done → post_version → (영상 생성) → video_done + video_url**
    
    ---
    
    ## 1️⃣ POST `/post_job`
    
    ### 역할
    
    - job 생성
    - **가사 생성 즉시 시작**
    
    ### Request (프론트 → 백)
    
    ```json
    {
    "guidelines":"...",
    "length":"30s",
    "selectedStyles":["minimal"],
    "selectedGenres":"hiphop",
    "additionalRequirements":""
    }
    
    ```
    
    ### Response
    
    ```json
    {
    "job_id":"abc123"
    }
    
    ```
    
    ### 백 내부 상태 (dict 예시)
    
    ```python
    jobs[job_id] = {
    "status":"lyrics_processing",
    "progress":0.0,
    "lyrics":None,
    "selected_version":None,
    "video_url":None
    }
    
    ```
    
    ---
    
    ## 2️⃣ GET `/job_status/{job_id}` ← ⭐ **프론트 polling 핵심**
    
    > 이 endpoint 하나만 계속 두드리면 됨
    > 
    
    ### 가사 생성 중
    
    ```json
    {
    "status":"lyrics_processing",
    "progress":0.3
    }
    
    ```
    
    ### 가사 생성 완료
    
    ```json
    {
    "status":"lyrics_done",
    "lyrics":{
    "v1":"가사 버전 1 텍스트...",
    "v2":"가사 버전 2 텍스트..."
    }
    }
    
    ```
    
    → 프론트는 이 시점에 **lyricselection UI 표시**
    
    ---
    
    ## 3️⃣ POST `/post_version`
    
    ### 역할
    
    - 사용자가 고른 가사 버전 전달
    - **즉시 영상 생성 시작**
    
    ### Request
    
    ```json
    {
    "job_id":"abc123",
    "version":1
    }
    
    ```
    
    ### Response
    
    ```json
    {
    "ok":true
    }
    
    ```
    
    ### 백 내부 상태 변경
    
    ```python
    jobs[job_id]["status"] ="video_processing"
    jobs[job_id]["selected_version"] =1
    
    ```
    
    ---
    
    ## 4️⃣ GET `/job_status/{job_id}` (계속 polling)
    
    ### 영상 생성 중
    
    ```json
    {
    "status":"video_processing",
    "progress":0.6
    }
    
    ```
    
    ### 영상 생성 완료
    
    ```json
    {
    "status":"video_done",
    "video_url":"/outputs/abc123.mp4"
    }
    
    ```
    
    ---
    
    ## 5️⃣ 영상 서빙
    
    FastAPI:
    
    ```python
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
    
    ```
    
    Next rewrite:
    
    ```jsx
    {source:"/outputs/:path*",destination:"http://127.0.0.1:8000/outputs/:path*" }
    
    ```
    
    프론트:
    
    ```tsx
    <video src="/outputs/abc123.mp4" controls />
    
    ```

---

## Suno Music Generation (Backend Module)

### 목적
- Suno API를 통해 가사를 기반으로 음악을 생성하고, 콜백 완료 시 MinIO에 저장한다.

### 환경변수
- SUNO_API_KEY: Suno API 키 (필수)
- SUNO_CALLBACK_URL: 콜백 URL (필수, 외부 접근 가능한 HTTPS)
- SUNO_API_BASE: 기본값 `https://api.sunoapi.org`
- SUNO_MODEL: 기본값 `V4_5ALL`
- MINIO_BUCKET_MUSIC: 기본값 `safety-mv`

### 엔드포인트
- POST `/suno/generate`
  - Request:
    - `lyrics` (필수, 가사)
    - `style` (필수, 장르/무드)
    - `title` (필수)
    - `job_id` (optional)
    - `model` (optional)
    - 기타 옵션: `negative_tags`, `vocal_gender`, `style_weight`, `weirdness_constraint`, `audio_weight`, `persona_id`
  - Response:
    - `{ "task_id": "..." }`

- POST `/callbacks/suno/music`
  - Suno 콜백 수신 엔드포인트
  - `callbackType=complete`일 때 오디오/이미지를 내려받아 MinIO에 저장

- GET `/suno/tasks/{task_id}`
  - Suno task 상태/콜백 결과 확인

### 저장 규칙 (MinIO)
- 버킷: `MINIO_BUCKET_MUSIC` (기본 `safety-mv`)
- 경로:
  - 오디오: `suno/{job_id}/{task_id}/{track_id}.mp3`
  - 커버: `suno/{job_id}/{task_id}/{track_id}.jpg`

### 테스트 (frontend-suno)
- 프론트 경로: `frontend-suno`
- 실행:
  - `npm install`
  - `npm run dev`
- 접속:
  - `http://localhost:5174`
- API Base는 백엔드 주소 (기본 `http://127.0.0.1:8000`)
