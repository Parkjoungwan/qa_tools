# 실행 시나리오(설계)

1) (전제) 로그인 완료 상태에서 `/crc/list`에 도달.
2) `#weeksArea` 존재 확인(화면 준비 상태).
3) 주차=1,2 / 차시=1,2에 대해:
   a. 선택자 템플릿으로 앵커 목록 수집:
      `#weeksArea a.roundClass[data-week="{w}"][data-round="{r}"]`
   b. 각 앵커 클릭(오토웨이트에 의존해 안정화).  
   c. `form#infoForm`이 **보일 때까지** 기다림(가시성 어서션).
   d. **폼 엘리먼트만** 캡처 → `artifacts/forms/form_w{w}_r{r}_{codeSlug}.png`.
   e. 다음 앵커로 진행(폼이 갱신되는 유형이면 동일 셀렉터로 재평가).

비고:
- Playwright의 웹 전용 어서션(`to_be_visible`, `to_have_url`)은 **조건 만족까지 자동 대기**한다.
- 클릭은 **액셔너빌리티/오토스크롤** 체크 후 실행된다(수동 스크롤 불필요).
