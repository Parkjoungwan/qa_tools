# CI 매트릭스/아티팩트 계획 (초안)

- 브라우저: Chromium (필요 시 Firefox/WebKit 추가)
- OS: 리눅스(기본), 로컬 맥 개발환경은 수동 확인
- 아티팩트:
  - 성공: 선택적 캡처
  - 실패: 페이지 캡처(뷰포트/필요 시 전체), 콘솔 로그
- 시크릿: BASE_URL / LOGIN_ID / LOGIN_PW → CI Secrets로 주입
