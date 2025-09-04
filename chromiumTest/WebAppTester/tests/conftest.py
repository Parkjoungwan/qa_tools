
import pytest
import re
from pathlib import Path
from playwright.sync_api import Page, expect
from WebAppTester.src.spec_loader import load_spec
from WebAppTester.src.config import AppConfig

# 프로젝트 루트를 기준으로 로그인 스펙 경로 설정
LOGIN_SPEC_PATH = Path(__file__).parent.parent / "routes" / "login" / "spec.yaml"

@pytest.fixture(scope="function")
def logged_in_page(page: Page, browser_context_args):
    """
    로그인을 먼저 수행하고, 로그인된 상태의 page 객체를 반환하는 Fixture.
    세션 스코프로 설정하여 테스트 세션 당 한 번만 로그인합니다.
    """
    login_spec = load_spec(str(LOGIN_SPEC_PATH))
    
    spec_nav = login_spec['navigations']
    spec_fields = login_spec['fields']
    spec_actions = login_spec['actions']
    
    # AppConfig를 통해 환경 변수 로드
    config = AppConfig(login_spec['env']['keys'])

    # 1. 로그인 페이지로 이동
    page.goto(spec_nav['entry_url'])

    # 2. 필드 값 입력
    for field in spec_fields:
        page.locator(field['selector']).fill(config.get(field['value_from_env']))

    # 3. 제출 액션 수행
    submit_action = spec_actions['submit']['by']
    if submit_action['type'] == 'css':
        page.locator(submit_action['selector']).click()
    elif submit_action['type'] == 'role':
        page.get_by_role(submit_action['role'], name=submit_action['name']).click()

    # 4. 성공 URL 검증 및 페이지 준비 상태 확인 (자동 대기)
    expect(page).to_have_url(re.compile(spec_nav['success_url_regex']))
    expect(page.locator("#weeksArea")).to_be_visible()
    
    print("\n(Fixture) 로그인 및 /crc/list 페이지 로딩 성공. 이후 테스트 진행.")

    yield page
