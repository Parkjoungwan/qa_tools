import pytest
import re
from playwright.sync_api import Page, expect, Locator
from pathlib import Path
from WebAppTester.src.spec_loader import load_spec
from WebAppTester.src.utils import slugify

# 테스트 대상 스펙 파일 경로
SPEC_PATH = Path(__file__).parent.parent / "routes" / "crc_list" / "spec.yaml"

@pytest.fixture(scope="module")
def crc_list_spec():
    """crc_list 스펙 파일을 로드하여 테스트에 제공하는 Fixture"""
    return load_spec(str(SPEC_PATH))

def test_crc_list_interaction(logged_in_page: Page, crc_list_spec: dict):
    """
    로그인된 페이지에서 crc/list 스펙에 따라 각 항목을 클릭하고 폼을 캡처합니다.
    """
    page = logged_in_page
    spec_nav = crc_list_spec['navigations']
    spec_scope = crc_list_spec['scope']
    spec_interact = crc_list_spec['interaction']
    spec_artifact = crc_list_spec['artifact']

    # 1. /crc/list 페이지로 이동 및 준비 상태 확인 (Fixture에서 이미 수행)
    # page.goto(spec_nav['entry_url'])
    # ready_indicator = spec_nav['ready_indicator']
    # try:
    #     expect(page.locator(ready_indicator['selector'])).to_be_visible()
    # except AssertionError as e:
    #     page.screenshot(path="crc_list_failure_debug.png")
    #     print("\n[Debug] /crc/list 페이지 준비 상태 검증 실패. crc_list_failure_debug.png 파일을 확인하세요.")
    #     raise e

    # 2. 실제 데이터가 로딩될 때까지 대기
    # "1주차"라는 텍스트를 가진 첫 번째 dt 태그를 기다린다.
    expect(page.locator("#weeksArea dt", has_text="1주차").first).to_be_visible()

    # 3. 주차와 차시를 기준으로 루프를 돌며 테스트 진행
    weeks_to_test = spec_scope['weeks']
    rounds_to_test = spec_scope['rounds']
    form_locator = page.locator(spec_interact['wait_for_form']['selector'])
    output_dir = Path(spec_artifact['screenshot']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    WAIT_TIMEOUT = spec_interact.get('wait_for_form', {}).get('timeout_ms', 10_000)

    def form_signature(p: Page) -> str:
        # 폼이 없으면 'NONE', 있으면 텍스트 일부 + 자식 수로 간단 시그니처 생성
        return p.evaluate("""() => {
            const f = document.querySelector('form#infoForm');
            if (!f) return 'NONE';
            const t = (f.innerText || '').slice(0, 200);
            return t + '|' + f.childElementCount;
        }""")

    for week in weeks_to_test:
        for round_val in rounds_to_test:
            group_selector = f"#weeksArea a.roundClass[data-week='{week}'][data-round='{round_val}']"
            anchors_in_group = page.locator(group_selector).all()
            
            print(f"\n[Debug] Testing group: week={week}, round={round_val}. Found {len(anchors_in_group)} items.")

            for anchor in anchors_in_group:
                # --- 클릭 전: 이전 폼 시그니처 확보
                prev_sig = form_signature(page)

                # 클릭 대상의 '이름 토큰' 선정 (앵커 텍스트 우선, 없으면 data-code)
                anchor_text = (anchor.text_content() or "").strip()
                name_token = anchor_text or (anchor.get_attribute(crc_list_spec['name_source']['anchor_text_fallback_to']) or "").strip()

                # --- 클릭
                anchor.click()

                # --- 폼 보임 대기 (기본 가시성)
                expect(form_locator).to_be_visible(timeout=WAIT_TIMEOUT)

                # --- 1순위: 폼이 '방금 클릭한 항목'으로 갱신되었는지 내용 기준 대기
                try:
                    page.wait_for_function(
                        "token => {\n                            const f = document.querySelector('form#infoForm');\n                            if (!f) return false;\n                            const txt = f.innerText || '';\n                            return token && txt.includes(token);\n                        }",
                        arg=name_token,
                        timeout=WAIT_TIMEOUT
                    )
                except Exception:
                    # --- 2순위(폴백): 폼 시그니처가 이전과 달라질 때까지 대기
                    page.wait_for_function(
                        "prev => {\n                            const f = document.querySelector('form#infoForm');\n                            if (!f) return false;\n                            const cur = (f.innerText || '').slice(0, 200) + '|' + f.childElementCount;\n                            return cur !== prev;\n                        }",
                        arg=prev_sig,
                        timeout=WAIT_TIMEOUT
                    )

                # --- 파일명 생성
                filename = (
                    spec_artifact['screenshot']['filename_template']
                    .replace("{{week}}", str(week))
                    .replace("{{round}}", str(round_val))
                    .replace("{{code|slug}}", slugify(name_token))
                )

                # --- 엘리먼트 스크린샷
                screenshot_path = output_dir / filename
                form_locator.screenshot(path=str(screenshot_path))
                print(f"Captured: {screenshot_path}")