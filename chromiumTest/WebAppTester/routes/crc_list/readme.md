# /crc/list 라우터 — 주차/차시 컨텐츠 진입 & 폼 로딩 확인

## 목적
- 1주차·2주차, (옵션) 1·2차시의 각 항목(anchor)을 클릭.
- 하단 `form#infoForm`가 생성·표시되면 **폼만 엘리먼트 캡처**.
- 파일명은 `form_w{week}_r{round}_{code}.png` 규칙(앵커 텍스트를 slug 처리해 사용, 없으면 `data-code` 사용).

## 대상 탐색 규칙
- 기본 룰: `#weeksArea a.roundClass` 중 `data-week ∈ {1,2}` AND `data-round ∈ {1,2}`.
- 필요 시 `data-code` 화이트리스트/블랙리스트로 좁힐 수 있음.
- **CSS 속성 선택자**: `[data-week="1"]`, `[data-round="2"]` 등.
- **data-***는 DOM의 `dataset`으로 접근/검증 가능.

## 상호작용 & 동기화
- 클릭 전용 대기는 불필요: Playwright가 **오토웨이트**로 요소가 액션 가능할 때까지 기다렸다가 클릭함.
- 폼 로딩 완료 판정: `form#infoForm` **가시성 어서션**(`to_be_visible`).

## 캡처 정책
- **엘리먼트 스크린샷**: `form#infoForm`만 캡처. 필요 시 전후 스크린샷도 확장 가능.
