from playwright.sync_api import sync_playwright, expect

def run(playwright):
    # Chromium 브라우저를 실행
    browser = playwright.chromium.launch(headless=False) # headless=False로 하면 브라우저가 눈에 보입니다.
    page = browser.new_page()

    # Playwright 공식 문서 페이지로 이동
    page.goto("https://playwright.dev/python")

    # 페이지 제목이 "Playwright"를 포함하는지 확인
    import re
    expect(page).to_have_title(re.compile("Playwright"))

    # 'Get started' 링크를 찾아 클릭
    get_started_link = page.get_by_role("link", name="Get started")
    get_started_link.click()

    # "Installation"이라는 텍스트가 보이는지 확인
    expect(page.get_by_role("heading", name="Installation")).to_be_visible()

    # 스크린샷을 찍어 'example.png' 파일로 저장
    page.screenshot(path="example.png")
    print("스크린샷 'example.png'이 저장되었습니다.")

    # 브라우저 종료
    browser.close()

with sync_playwright() as playwright:
    run(playwright)