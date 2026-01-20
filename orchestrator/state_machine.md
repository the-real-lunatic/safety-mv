# State Machine — Safety MV AI

본 문서는 시스템의 상태 전이를 정의한다.
각 상태는 "행위"가 아니라 "확정된 결과"를 의미한다.

---

INIT
→ CONCEPT_GEN
→ QA
   → PASS → HITL
   → FAIL → (RETRY ≤ 1) → CONCEPT_GEN
→ LOCK_BLUEPRINT_CORE
→ STYLE_BIND
→ PARALLEL_MEDIA_GEN
→ RENDER
→ DONE