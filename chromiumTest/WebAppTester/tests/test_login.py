import pytest
import re
from playwright.sync_api import Page, expect
from pathlib import Path
from WebAppTester.src.spec_loader import load_spec

# 테스트 대상 스펙 파일 경로
# 이 테스트 파일의 위치(WebAppTester/tests)를 기준으로 상대 경로 설정
SPEC_PATH = Path(__file__).parent.parent / "routes" / "login" / "spec.yaml"

@pytest.fixture(scope="module")
def login_spec():
    """YAML 스펙 파일을 로드하여 테스트에 제공하는 Fixture"""
    return load_spec(str(SPEC_PATH))

def test_login_scenario(page: Page, login_spec: dict):
    """
    spec.yaml에 정의된 명세를 기반으로 로그인 E2E 테스트를 수행합니다.
    """
    spec_nav = login_spec['navigations']
    spec_fields = login_spec['fields']
    spec_actions = login_spec['actions']
    spec_success = login_spec['success_indicators']
    spec_artifacts = login_spec.get('artifacts', {}).get('screenshots', [])

    # 1. 진입 페이지로 이동
    page.goto(spec_nav['entry_url'])

    # (캡처) 페이지 진입 후 스크린샷
    entry_screenshot = next((s for s in spec_artifacts if s['url'] in spec_nav['entry_url']), None)
    if entry_screenshot:
        screenshot_path = Path("artifacts") / entry_screenshot['filename']
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=entry_screenshot['fullPage'])

    # 2. 필드 값 입력
    # spec.yaml에는 LOGIN_ID, LOGIN_PW 값이 없으므로, spec_loader가 치환한 값을 사용하지 않음
    # AppConfig를 통해 직접 환경 변수 값을 가져와야 함 (spec_loader 개선 필요)
    # 우선은 spec에 정의된 selector만 활용
    from WebAppTester.src.config import AppConfig
    config = AppConfig(login_spec['env']['keys'])

    for field in spec_fields:
        page.locator(field['selector']).fill(config.get(field['value_from_env']))

    # 3. 제출 액션 수행
    submit_action = spec_actions['submit']['by']
    if submit_action['type'] == 'css':
        page.locator(submit_action['selector']).click()
    elif submit_action['type'] == 'role':
        page.get_by_role(submit_action['role'], name=submit_action['name']).click()

    # 4. 성공 URL 검증 (자동 대기)
    expect(page).to_have_url(re.compile(spec_nav['success_url_regex']))

    # 5. 보조 성공 지표 검증 (자동 대기)
    # for indicator in spec_success:
    #     if indicator['type'] == 'role':
    #         locator = page.get_by_role(indicator['role'], name=indicator['name'])
    #         expect(locator).to_be_visible()

    # (캡처) 성공 페이지 스크린샷
    success_screenshot = next((s for s in spec_artifacts if s['url'] in page.url), None)
    if success_screenshot:
        screenshot_path = Path("artifacts") / success_screenshot['filename']
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=success_screenshot['fullPage'])

    print("\n로그인 테스트 성공!")