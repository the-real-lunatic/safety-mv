# 🎵 Rule2Chant
### 규정 문서를, 사람이 기억하는 경험으로 바꾸는 멀티에이전트 시스템

> **TL;DR**  
> 긴 규정 PDF를 입력하면,  
> AI가 핵심을 추출하고 여러 후보를 만들고 검수한 뒤,  
> **1분짜리 ‘뮤직비디오용 가사 + 영상 시안’ 2가지를 제안**합니다.  
> 최종 선택은 **사람(Human-in-the-loop)** 이 합니다.

---

## 🚀 Demo First (가장 중요)

> ⚠️ 실제 README에서는 이 섹션이 **최상단**에 와야 합니다.

### 🎬 Hook Demo (15–20 sec)
> 📍 **여기에 Hook 영상 삽입 (자동 재생 or 클릭 재생)**  
> - 예: “안전 규정으로 만든 트로트 훅 영상”
>
> (GitHub에서는 mp4 링크를 붙이면 자동 플레이어가 생성됩니다.)


---

## 🤔 문제 정의: 왜 규정 문서는 실패하는가?

기업과 조직에는 수많은 규정, 정책, 온보딩 문서가 존재합니다.

- 안전 규정
- 물류/배송 매뉴얼
- 개발자 온보딩 가이드
- 내부 운영 정책

하지만 현실에서는:
- 문서는 **길고**
- 읽히지 않으며
- 읽혔다 해도 **기억되지 않습니다**

> **문제는 이해가 아니라 ‘기억’입니다.**

---

## 💡 우리의 접근: 문서를 요약하지 않는다

우리는 문서를 단순 요약하지 않습니다.

대신 다음 질문을 던집니다:

> “이 문서에서,  
> **사람이 1분 안에 꼭 기억해야 할 건 무엇인가?**”

그리고 그 핵심을:
- 가사 (lyrics)
- 반복되는 훅 (hook)
- 15초 단위 장면 시안 (video draft)

으로 재구성합니다.

---

## 🎶 왜 ‘뮤직비디오’인가?

텍스트보다 **리듬과 반복**이 더 오래 남습니다.

- 문서 ❌  
- 체크리스트 ❌  
- 교육 영상 ❌  

대신:
- **노래 한 소절**
- **반복되는 훅**
- **짧은 장면**

이 실제 행동 변화를 만듭니다.

---

## 🧠 시스템 개요 (Multi-Agent Pipeline)

이 시스템은 단일 LLM 호출이 아니라,  
**여러 에이전트가 역할을 나눠 협업하는 구조**입니다.

### 🔍 전체 파이프라인 개요


---

## 🧩 Multi-Agent 설계 포인트

이 문제는 단일 LLM 호출로 해결할 수 있는 문제가 아니라고 판단했습니다.  
문서의 핵심을 “생성”하는 것보다, **문서와 실제로 일치하는지를 반복적으로 검증하고 조정하는 과정**이 더 중요했기 때문입니다.

그래서 저희는 오전 세션에서 배운 멀티에이전트 디자인 패턴 중  
**PEV (Propose–Evaluate–Verify)**, **Worker–Manager**,  
그리고 세션에서는 다루지 않았지만 실무에서 필수적인 **HITL (Human-in-the-Loop)** 패턴을 조합하여 사용했습니다.

---

### 1. PEV 패턴 (Propose – Evaluate – Verify)

첫 번째로, 생성된 가사와 뮤직비디오 시안이 **실제 입력 문서의 내용과 일치하는지 검증**하기 위해  
PEV 구조를 도입했습니다.

<img width="520" height="650" alt="image" src="https://github.com/user-attachments/assets/08995a54-a72e-4b03-aa0c-67351c5513f0" />


- **Propose**  
  - 하나의 결과를 바로 생성하지 않고,  
    가사 + 영상 시안을 **여러 개(K개)** 후보로 생성합니다.

- **Evaluate**  
  - 각 후보가 문서의 핵심 원칙과 얼마나 정합적인지 QA를 수행합니다.
  - 문서에 없는 내용(환각), 핵심 규칙 누락 여부를 점검합니다.
  - “1분짜리 콘텐츠로 전달 가능한지”도 함께 평가합니다.

- **Verify / Revise**  
  - QA 결과를 바탕으로 후보를 수정하고 다시 검증합니다.
  - 이 과정을 **2–3회 반복**하여, 문서와 가장 잘 맞는 후보들만 남깁니다.

이 구조를 통해 “그럴듯한 결과”가 아니라,  
**문서에 근거한 결과**를 만들 수 있도록 했습니다.

---

### 2. Human-in-the-Loop (HITL)

<img width="528" height="768" alt="image" src="https://github.com/user-attachments/assets/33b9d5e4-3d2c-486d-bdb8-ee1d2e39710e" />


두 번째로, AI가 만든 결과를 **사람이 직접 평가하고 선택할 수 있도록**  
Human-in-the-Loop 패턴을 필수 단계로 넣었습니다.

- 반복적인 QA 루프 이후, **최종 2개의 시안**만 사람에게 제시합니다.
- AI는 추천만 하고, **최종 선택은 사람이 수행**합니다.
- 이를 통해:
  - 기업/사내 환경에서 요구되는 책임성과 신뢰성을 확보하고
  - “AI가 마음대로 만든 결과”라는 인상을 제거합니다.

저희는 이 단계를 선택 사항이 아닌 **필수 단계**로 설계했습니다.

---

### 3. Worker–Manager 패턴 (멀티모달 한계 극복)

<img width="504" height="660" alt="image" src="https://github.com/user-attachments/assets/f3d8063a-526b-4775-b5ac-924cb3dcfcb6" />


마지막으로, 현재 멀티모달 모델의 한계를 고려해  
Worker–Manager 패턴을 적용했습니다.

현재의 멀티모달 생성은 다음과 같은 제약이 있습니다.

- 영상 생성은 **짧은 클립 단위(약 10–12초)**로 제한됨
- 음악과 영상 생성이 **서로 분리된 작업**임
- 긴 문맥과 일관성을 단일 에이전트가 유지하기 어려움

이를 해결하기 위해:

- Manager(Orchestrator)가 전체 시안을 기준으로 작업을 관리하고
- 여러 **Worker**가 병렬적으로 작업을 수행합니다.
  - 캐릭터 생성 Worker
  - 영상 생성 Worker (12초 클립 × 여러 개 병렬)
  - 음악 생성 Worker
- 생성된 결과는 **Combiner**에서 하나의 뮤직비디오로 합쳐집니다.

이 구조를 통해:
- 각 모달리티의 한계를 인정하고
- 대신 **조율과 관리로 일관성을 확보**하는 방향을 선택했습니다.

---

### 요약

- 이 문제는 **요약 문제가 아니라 판단 문제**이기 때문에,
- 생성 → 검증 → 수정 → 선택의 구조가 필요했고,
- 이를 위해 **PEV + HITL + Worker–Manager** 패턴을 결합했습니다.

> 단일 에이전트가 “잘 만들어주길 기대하는 것”이 아니라,  
> 여러 에이전트가 협업하며 **신뢰 가능한 결과에 수렴하도록 설계**했습니다.

### 전체 파이프라인

<img width="1536" height="1024" alt="ChatGPT Image 2026년 1월 20일 오후 04_57_30" src="https://github.com/user-attachments/assets/f464846f-a258-4321-8df7-8cc5e9a8420f" />


## 🏁 결론

> **우리는 문서를 요약하지 않습니다.**  
> **문서를, 사람이 기억하는 경험으로 바꿉니다.**

---

## ▶️ 실행 방법 (Local)

```bash
# 1) 환경 변수 설정 (.env)
GPT_API_KEY=your_api_key_here
SORA_API_KEY=your_api_key_here
SUNO_API_KEY=your_api_key_here
SORA_API_BASE=https://api.openai.com/v1
SORA_IMAGE_ENDPOINT=/images/generations
SORA_VIDEO_ENDPOINT=/videos

# 2) 실행
docker compose up --build

# 3) Job 생성 (예: 텍스트)
curl -s -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "guidelines":"작업 전 보호구를 착용한다. 위험 구역 출입 금지.",
    "length":"30s",
    "selectedStyles":["minimal","modern"],
    "selectedGenres":"hiphop",
    "additionalRequirements":"가사는 한국어",
    "llm_model":"gpt-4o-mini",
    "llm_temperature":0.4,
    "hitl_mode":"required"
  }'

# 4) 상태 확인
curl -s http://localhost:8000/jobs/{job_id}
```
