# Strategy 디렉터리 안내

## 목적
- 전략별 구현을 파일 단위로 분리해 유지보수와 확장을 쉽게 한다.
- 각 전략 문서는 **한글 설명 + LLM 프롬프트 템플릿 + 다이어그램**을 포함한다.

## 전략 목록 (strategy_id)
- origin: 원안 레퍼런스
- parallel_stylelock: 병렬 생성 + 스타일 락
- sequential_anchor: 순차 앵커
- hybrid_overlap: 오디오-우선 + 오버랩
- storyboard_keyframes: 스토리보드 키프레임
- mix_audio_anchor: 오디오-우선 + 앵커 주입
- video_chain: 비디오 체인

## 규칙
- **strategy_id = 파일명(확장자 제외)**
- 전략 파일은 `strategies/<strategy_id>.md`
- 백엔드는 `strategies/` 하위의 `.md` 파일을 읽어 전략 목록을 구성
