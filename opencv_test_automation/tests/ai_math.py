# tests/ai_math.py
"""
AI Math 자동화 (스와이프 끝 감지 + start/grade 엄격 + 오프셋)
──────────────────────────────────────────────────────────────
업데이트
1️⃣  스와이프 후 애니메이션 여유 0.9 s  (기존 0.6 s)  
5️⃣  스와이프 뒤 첫 매칭 실패 시, start 버튼 임계값을 0.90 으로 한 번 더 재시도
"""

from pathlib import Path
import time, cv2, os, numpy as np
from dotenv import load_dotenv
from opencv_test_automation.utils import adb_utils, image_matcher, page_utils

# ───────── .env 기기 지정 ──────────────────────────────
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")

# ───────── 경로 정의 ───────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent # tests/ai_math.py -> tests -> opencv_test_automation
BTN_START  = ROOT / "images" / "ai_math" / "start.png"
BTN_GRADE  = ROOT / "images" / "ai_math" / "grade.png"
GRADES     = [ROOT / "images" / "ai_math" / f"grade_{i}.png" for i in range(1, 7)]

LOOP_TEMPLATES = [
    ROOT / "images" / "ai_math" / "check.png",
    ROOT / "images" / "ai_math" / "force_yes.png",
    ROOT / "images" / "ai_math" / "next.png",
]
TAIL_TEMPLATES = [
    ROOT / "images" / "ai_math" / "confirm.png",
    ROOT / "images" / "ai_math" / "down_navi.png",
    ROOT / "images" / "ai_math" / "navi_close.png",
    ROOT / "images" / "ai_math" / "end.png",
]

LOADING_IMG = ROOT / "images" / "ai_math" / "loading.png"

# ───────── 파라미터 ────────────────────────────────────
THRESHOLD        = 0.85
START_TH         = 0.93          # 기본 start 임계값
START_TH_LOOSE   = 0.90          # 스와이프 뒤 재시도 임계값  ★
GRADE_TH         = 0.92
ROI_MARGIN       = 20
SCREEN_DIFF_TH   = 0.005
POS_CACHE: dict[Path, tuple[int, int]] = {}

SCR_W, SCR_H     = 1080, 1920
SWIPE_START      = (int(SCR_W * 0.80), SCR_H // 2)
SWIPE_END        = (int(SCR_W * 0.20), SCR_H // 2)
MAX_SWIPE        = 5
GRADE_Y_OFFSET   = -20

# ───────── 헬퍼 ────────────────────────────────────────
def wait_loading_gone(timeout=40.0):
    def _vis():
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, 0.65) is not None
    adb_utils.wait_until(lambda: not _vis(), timeout, 0.7)

def screens_similar(p1, p2):
    a, b = cv2.imread(p1), cv2.imread(p2)
    if a is None or b is None or a.shape != b.shape:
        return False
    return np.sum(cv2.absdiff(a, b)) / (a.size * 255) < SCREEN_DIFF_TH

def _quick(tpl, scr, pos, th):
    tpl_i = cv2.imread(str(tpl)); scr_i = cv2.imread(str(scr))
    if tpl_i is None or scr_i is None:
        return False
    h, w = tpl_i.shape[:2]; cx, cy = pos
    y1 = max(cy-h//2-ROI_MARGIN, 0); x1 = max(cx-w//2-ROI_MARGIN, 0)
    y2 = min(cy+h//2+ROI_MARGIN, scr_i.shape[0])
    x2 = min(cx+w//2+ROI_MARGIN, scr_i.shape[1])
    roi = scr_i[y1:y2, x1:x2]
    if roi.size == 0:
        return False
    return cv2.minMaxLoc(cv2.matchTemplate(roi, tpl_i, cv2.TM_CCOEFF_NORMED))[1] >= th

def tap_template(tpl: Path, *, timeout=12, th=THRESHOLD, off=(0, 0)):
    def _tap():
        scr = adb_utils.capture_screen()
        if tpl in POS_CACHE and _quick(tpl, scr, POS_CACHE[tpl], th):
            x, y = POS_CACHE[tpl]
        else:
            pos = image_matcher.find_template_on_screen(tpl, scr, th)
            if not pos:
                return False
            POS_CACHE[tpl] = pos
            x, y = pos
        adb_utils.tap(x + off[0], y + off[1]); return True
    if not adb_utils.wait_until(_tap, timeout, 0.5):
        raise RuntimeError(f"[탭 실패] {tpl}")

# ───────── 스와이프 + start 탐색 ────────────────────────
def swipe_once_and_try_start(prev_scr: str) -> tuple[bool | None, str]:
    adb_utils.swipe(*SWIPE_START, *SWIPE_END, 300)
    time.sleep(1.5)                                      # ★ 1) 슬립 0.9 s
    new_scr = adb_utils.capture_screen()
    if screens_similar(prev_scr, new_scr):
        return False, new_scr
    # 1차(기존 임계값)
    try:
        tap_template(BTN_START, timeout=2, th=START_TH)
        return True, new_scr
    except RuntimeError:
        pass
    # 2차(느슨 임계값 0.90)
    try:
        tap_template(BTN_START, timeout=2, th=START_TH_LOOSE)  # ★ 5) 낮춘 임계값
        return True, new_scr
    except RuntimeError:
        return None, new_scr

def try_find_start_with_swipes() -> bool:
    try:
        tap_template(BTN_START, timeout=2, th=START_TH)
        return True
    except RuntimeError:
        pass
    prev = adb_utils.capture_screen()
    for _ in range(MAX_SWIPE):
        res, prev = swipe_once_and_try_start(prev)
        if res is True:
            return True
        if res is False:
            break
    return False

# ───────── start + grade 루틴 ──────────────────────────
def handle_start_button():
    if try_find_start_with_swipes():
        return
    for idx, g_tpl in enumerate(GRADES, 1):
        print(f"⚙️ grade_{idx} 선택")
        tap_template(BTN_GRADE, th=GRADE_TH, off=(0, GRADE_Y_OFFSET))
        time.sleep(0.2)
        tap_template(g_tpl)
        time.sleep(0.6); wait_loading_gone()
        if try_find_start_with_swipes():
            return
    raise RuntimeError("start 버튼을 모든 grade에서 찾지 못했습니다.")

# ───────── ai_math 진입 (다른 페이지 → ai_math) ────────
def goto_ai_math():
    cur, _ = page_utils.detect_current_page()
    if cur == "ai_math":
        print("📍 이미 ai_math 페이지")
        return
    btn = ROOT / "images" / cur / "ai_math.png"
    if not btn.exists():
        raise RuntimeError(f"{cur} → ai_math 버튼 없음")
    print(f"➡️  {cur} → ai_math 이동")
    tap_template(btn); wait_loading_gone()
    if page_utils.detect_current_page()[0] != "ai_math":
        raise RuntimeError("ai_math 이동 실패")

# ───────── 메인 플로우 ──────────────────────────────────
def run_ai_math_flow():
    goto_ai_math(); time.sleep(0.6); wait_loading_gone()
    handle_start_button(); time.sleep(0.6); wait_loading_gone()

    for i in range(10):
        print(f"🔄 반복 {i+1}/10")
        for tpl in LOOP_TEMPLATES:
            tap_template(tpl); time.sleep(0.4); wait_loading_gone()

    print("🎯 마무리 단계")
    for tpl in TAIL_TEMPLATES:
        tap_template(tpl); time.sleep(0.4); wait_loading_gone()

# ───────── 실행 ────────────────────────────────────────
if __name__ == "__main__":
    start = time.time()
    try:
        run_ai_math_flow()
        print(f"\n✅ 완료! 총 소요 {time.time()-start:.2f}s")
    except Exception as e:
        print(f"\n❌ 실패: {e} ({time.time()-start:.2f}s)")

