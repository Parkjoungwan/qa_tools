# 셀렉터 정책 (우선순위)

1) **접근성 기반**: `get_by_role(role, name)` / `get_by_label` / `get_by_placeholder`
2) **테스트 ID**: `data-testid` 또는 `data-pw` (컴포넌트 경계 안정화 용도)
3) **명시적 선택자**: id/CSS (예: `#btnLogin`) — 초기 안정화/마이그레이션 단계에서만 사용

> 이유: 접근성 기반 로케이터는 사용자 인식과 일치하고, Playwright의 자동 대기(오토웨이트) 및 웹 전용 어서션과 궁합이 좋음.

# crc_list 특화 셀렉터 지침

- 기본: `#weeksArea a.roundClass`
- 필터: CSS 속성 선택자 `[data-week="1"][data-round="1"]`
- 파일명 토큰: 클릭한 앵커의 **텍스트** 우선, 없거나 공백이면 `data-code` 사용(슬러그 처리)

> 이유: data-*는 프론트가 상태를 넣어두는 관용적 표준이며, CSS 속성 선택자로 안정적으로 찾을 수 있음.