# 실행 시나리오(로그인 스모크) — 설계

1. `${BASE_URL}/login` 진입
2. `#loginId`에 `LOGIN_ID`, `#pwd`에 `LOGIN_PW` 입력
3. `#btnLogin` 클릭
4. `to_have_url(/.*\/crc\/list$/)` 성공 판정
5. (보조) 성공 화면 지표 `to_be_visible()` 확인
6. 캡처: login_viewport.png / crc_list_full.png

> 주: Playwright의 웹 전용 어서션은 조건 만족까지 자동 대기함.