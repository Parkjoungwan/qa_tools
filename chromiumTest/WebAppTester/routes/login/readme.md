# /login 라우터 스펙 개요

## 목적
- `${BASE_URL}/login` 진입 후 `#loginId`, `#pwd`에 자격 증명 입력 → `#btnLogin` 클릭.
- 성공 시 `/crc/list`로 이동했음을 URL 정규식으로 판정하고, 보조 지표(헤딩/메뉴)를 가시성으로 확인.

## 사전 조건
- .env 또는 CI Secrets: `BASE_URL`, `LOGIN_ID`, `LOGIN_PW`.
- 로그인 중 CAPTCHA/SSO/2FA가 있다면 테스트 환경에서 비활성 스위치 또는 모킹 경로 협의.

## 판정 규칙
- 1차: `to_have_url(/.*\/crc\/list$/)` 대기·검증.
- 2차(보조): 특정 헤딩/메뉴 `to_be_visible()`.

## 아티팩트
- 로그인 화면 뷰포트 캡처, 성공 후 목록 화면 전체 캡처.

## 확장 계획
- 음수 케이스(오류 메시지, 잠금 등)는 별도 시나리오로 분리.
- 안정화 후 role 기반 로케이터(`get_by_role`)로 전환.