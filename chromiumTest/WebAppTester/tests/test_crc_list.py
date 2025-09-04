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

    # 3. 테스트 대상 앵커 목록 수집
    target_anchors = page.locator(spec_scope['discovery_selector']).all()
    print(f"\n[Debug] Found {len(target_anchors)} total anchors with selector: {spec_scope['discovery_selector']}")

    # 스펙에 정의된 주차(week)와 차시(round)로 필터링
    scoped_anchors = []
    for anchor in target_anchors:
        week = anchor.get_attribute("data-week")
        round_val = anchor.get_attribute("data-round")
        if week and round_val and int(week) in spec_scope['weeks'] and int(round_val) in spec_scope['rounds']:
            scoped_anchors.append(anchor)
    
    print(f"[Debug] Found {len(scoped_anchors)} anchors matching the scope (weeks={spec_scope['weeks']}, rounds={spec_scope['rounds']})")

    # 3. 각 앵커 순회하며 테스트 진행
    form_locator = page.locator(spec_interact['wait_for_form']['selector'])
    output_dir = Path(spec_artifact['screenshot']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)

    for anchor in scoped_anchors:
        # 4. 앵커 클릭
        anchor.click()

        # 5. 폼 로딩 대기 및 검증
        expect(form_locator).to_be_visible()

        # 6. 스크린샷 파일명 생성
        week = anchor.get_attribute("data-week")
        round_val = anchor.get_attribute("data-round")
        
        # 앵커 텍스트 또는 data-code로 파일명 결정
        anchor_text = anchor.text_content()
        if anchor_text and anchor_text.strip():
            name_token = anchor_text
        else:
            name_token = anchor.get_attribute(crc_list_spec['name_source']['anchor_text_fallback_to'])

        filename = (
            spec_artifact['screenshot']['filename_template']
            .replace("{{week}}", week)
            .replace("{{round}}", round_val)
            .replace("{{code|slug}}", slugify(name_token))
        )

        # 7. 폼 엘리먼트 스크린샷 캡처
        screenshot_path = output_dir / filename
        form_locator.screenshot(path=str(screenshot_path))
        print(f"Captured: {screenshot_path}")
