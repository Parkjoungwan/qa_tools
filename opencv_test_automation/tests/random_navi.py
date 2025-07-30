# tests/random_navi.py
"""
랜덤 페이지 네비게이션 v3.9
────────────────────────────────────────────────────────
• 현재 페이지(navi_origin) → 랜덤 다른 페이지 버튼 탭
• 버튼 경로  : images/<현재페이지>/<target>.png
• loading.png 이 보이면 '⌛ Loading… <sec>s' 주기 출력
• 목표 페이지 인식 실패 시
    ① images/out1.png → out3.png 순으로 눌러 홈으로 복귀
    ② loading 종료 대기 후 다시 인식
    ③ 그래도 실패면 예외 종료
※ page_utils.PAGES 가 set 이더라도 문제 없도록
  모두 리스트로 변환해 사용함.
"""

import os, time, random, argparse
from pathlib import Path
from dotenv import load_dotenv

from utils import adb_utils, image_matcher, page_utils

# ─────────────── 기기 지정 (.env) ──────────────────────
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")

# ─────────────── 정적 설정 ─────────────────────────────
BTN_FILE = {
    "main_10_default": "main_10.png",
    "subject_study":   "subject_study.png",
    "unit_master":     "unit_master.png",
    "ai_math":         "ai_math.png",
    "ai_exam":         "ai_exam.png",
    "knowledge_land":  "knowledge_land.png",
    "ai_report":       "ai_report.png",
}
OUT_BUTTONS = [Path("images/out1.png"),
               Path("images/out2.png"),
               Path("images/out3.png"),
               Path("images/out4.png"),
               Path("images/out5.png")]

MATCH_TH   = 0.85            # 일반 버튼 템플릿 임계값
LOADING_IMG = Path("images/loading.png")
LOADING_TH  = 0.65
RETRY_MAX   = 2              # 목표 페이지 인식 재시도 횟수

# ─────────────── 로딩 대기 ────────────────────────────
def wait_loading_gone(timeout: float, ping: float = 2.0):
    """loading.png 이 사라질 때까지 대기하며 상태 출력."""
    start = time.time()

    def visible() -> bool:
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, LOADING_TH) is not None

    last = start - ping
    while time.time() - start < timeout:
        if not visible():
            return
        if time.time() - last >= ping:
            print(f"⌛ Loading… {time.time()-start:.1f}s 경과")
            last = time.time()
        time.sleep(0.7)
    raise RuntimeError("로딩 타임아웃")

# ─────────────── 템플릿 탭 유틸 ────────────────────────
def tap_image(img: Path, th: float, timeout: float = 12) -> bool:
    """템플릿을 찾고 탭. 성공 True, 실패 False"""
    def _tap():
        scr = adb_utils.capture_screen()
        pos = image_matcher.find_template_on_screen(img, scr, th)
        if pos:
            adb_utils.tap(*pos); return True
        return False
    return adb_utils.wait_until(_tap, timeout, 0.7)

def tap_nav_button(cur_page: str, target_page: str):
    img = Path(f"images/{cur_page}/{BTN_FILE[target_page]}")
    if not img.exists():
        raise RuntimeError(f"버튼 이미지 없음: {img}")
    if not tap_image(img, MATCH_TH):
        raise RuntimeError(f"탭 실패: {img}")

# ─────────────── out 버튼 처리 ─────────────────────────
def try_out_buttons(load_timeout: float) -> bool:
    """out1→out3 순으로 눌러 홈 복귀. 하나라도 눌렀으면 True."""
    for img in OUT_BUTTONS:
        if img.exists() and tap_image(img, th=0.80, timeout=5):
            print(f"↩️ out 버튼 탭: {img.name}")
            wait_loading_gone(load_timeout / 2)      # out 뒤 짧게 대기
            return True
    return False

# ─────────────── 페이지 검증 ───────────────────────────
def verify_page(target: str) -> bool:
    """목표 페이지(navi_origin) 인식, RETRY_MAX 회 재시도."""
    for _ in range(RETRY_MAX + 1):
        page, _ = page_utils.detect_current_page()
        if page == target:
            return True
        time.sleep(2)
    return False

# ─────────────── 메인 로직 ─────────────────────────────
def run(num_iters: int, load_timeout: float):
    page_list = list(page_utils.PAGES)  # set → list
    for i in range(num_iters):
        # 현재 페이지 파악
        cur_page, _ = page_utils.detect_current_page()
        if not cur_page:
            print("⚠️ 현재 페이지 인식 실패 → out 시도")
            if try_out_buttons(load_timeout):
                cur_page, _ = page_utils.detect_current_page()
        if not cur_page:
            raise RuntimeError("현재 페이지 인식 실패 (out 처리 후에도)")

        # 목표 선택
        target_page = random.choice([p for p in page_list if p != cur_page])
        print(f"\n[{i+1}/{num_iters}] {cur_page} → {target_page}")

        # 버튼 탭 & 로딩
        tap_nav_button(cur_page, target_page)
        wait_loading_gone(load_timeout)

        # 목표 페이지 검증
        if verify_page(target_page):
            print(f"✅ {target_page} 도착"); continue

        # 실패 시 out 버튼 경유 재시도
        print("⚠️ 목표 인식 실패 → out 시도")
        if try_out_buttons(load_timeout) and verify_page(target_page):
            print(f"✅ {target_page} 도착( out 경유 )")
        else:
            raise RuntimeError(f"이동 실패: {target_page} 로 인식되지 않음")

# ─────────────── CLI 엔트리 ────────────────────────────
if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("--count", type=int, default=10,
                      help="이동 횟수 (기본 10)")
    argp.add_argument("--load-timeout", type=float, default=50,
                      help="loading 사라질 때까지 최대 대기 (초)")
    args = argp.parse_args()

    t0 = time.time()
    try:
        run(args.count, args.load_timeout)
        print(f"\n🎉 완료! 총 소요 {time.time()-t0:.2f}s")
    except Exception as e:
        print(f"\n❌ 실패: {e} ({time.time()-t0:.2f}s)")

