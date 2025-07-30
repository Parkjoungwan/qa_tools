# tests/page_detector.py
"""
현재 페이지(navi bar) 식별 테스트
────────────────────────────────────────────────────────
• 대상 폴더: main_10_default / subject_study / unit_master /
            ai_math / ai_exam / knowledge_land / ai_report
• 각 폴더 내 navi_origin.png 와 화면을 템플릿 매칭
• 가장 높은 상관계수(≥ 0.80) 를 갖는 폴더명을 '현재 페이지' 로 출력
"""

import cv2, os, time
from pathlib import Path
from dotenv import load_dotenv
from utils import adb_utils

# ── 1. 연결 기기 지정 (.env) ──────────────────────────
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")

# ── 2. 페이지 템플릿 목록 ────────────────────────────
PAGES = [
    "main_10_default",
    "subject_study",
    "unit_master",
    "ai_math",
    "ai_exam",
    "knowledge_land",
    "ai_report",
]

TEMPLATES = {
    page: Path(f"images/{page}/navi_origin.png") for page in PAGES
}
THRESHOLD = 0.80     # 최소 상관계수

# ── 3. 매칭 함수 ─────────────────────────────────────
def match_score(tpl_path: Path, screen_path: Path) -> float:
    tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
    scr = cv2.imread(str(screen_path), cv2.IMREAD_COLOR)
    if tpl is None or scr is None or scr.shape[0] < tpl.shape[0] or scr.shape[1] < tpl.shape[1]:
        return 0.0
    res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    return float(max_val)

# ── 4. 페이지 감지 ───────────────────────────────────
def detect_current_page():
    scr_path = adb_utils.capture_screen()
    best_page, best_score = None, 0.0

    for page, tpl in TEMPLATES.items():
        score = match_score(tpl, scr_path)
        print(f"{page:<16} → score {score:.3f}")
        if score > best_score:
            best_page, best_score = page, score

    if best_score >= THRESHOLD:
        return best_page, best_score
    return None, best_score

# ── 5. 실행부 ────────────────────────────────────────
if __name__ == "__main__":
    start = time.time()
    try:
        page, score = detect_current_page()
        if page:
            print(f"\n✅  현재 페이지: {page}  (score {score:.3f})")
        else:
            print("\n❓  일치하는 페이지를 찾지 못했습니다.")
        print(f"완료! 소요 {time.time()-start:.2f}s")
    except Exception as e:
        print(f"❌  실패: {e} ({time.time()-start:.2f}s)")

