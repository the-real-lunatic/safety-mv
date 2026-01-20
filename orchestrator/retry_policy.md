# Retry Policy

- 최대 재시도 횟수: 1
- 재시도 조건: QA fail
- 재시도 입력:
  - missing_keywords
  - structural_issues
- 목적:
  - 비용 폭증 방지
  - 지연 최소화

재시도 후에도 실패할 경우:
- 최고 점수 후보를 fallback으로 사용한다
- 이후 HITL 단계로 진행한다