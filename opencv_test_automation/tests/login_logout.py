"""
로그인 → (선택) 로그아웃
──────────────────────────────────────────────
• .env 파일에 **ID_1 / PW_1, ID_2 / PW_2, …** 형태로
  기기별 자격을 반드시 정의해야 합니다.
• LOGIN_INDEX 환경변수(1,2,3…)를 받아 해당 ID_n / PW_n만 사용하고,
  값이 없으면 바로 오류를 내도록 변경했습니다.
• CLI 인자
    0  : 로그인만
    1  : 로그인+로그아웃 (기본값)
"""

import time, os, sys
from pathlib import Path
from dotenv import load_dotenv

from opencv_test_automation.utils import adb_utils, image_matcher

# ───────────────── 셋업 ────────────────────────
load_dotenv()

LOGIN_IDX = os.getenv("LOGIN_INDEX")  # 반드시 1,2,3…
if not LOGIN_IDX or not LOGIN_IDX.isdigit():
    raise RuntimeError("LOGIN_INDEX 환경변수가 정의되지 않았습니다.")

USER_ID = os.getenv(f"ID_{LOGIN_IDX}")
USER_PW = os.getenv(f"PW_{LOGIN_IDX}")
if not USER_ID or not USER_PW:
    raise RuntimeError(f".env 에 ID_{LOGIN_IDX} / PW_{LOGIN_IDX} 가 없습니다.")

print(f"🔐  LOGIN_INDEX={LOGIN_IDX} → ID_{LOGIN_IDX}")

ROOT = Path(__file__).resolve().parent.parent

# ─────────── 이미지 템플릿 ───────────
IMG_LOGIN_ID     = ROOT / "images" / "login" / "id.png"
IMG_LOGIN_PW     = ROOT / "images" / "login" / "pw.png"
IMG_LOGIN_BTN    = ROOT / "images" / "login" / "btn.png"
IMG_LOGIN_LATER  = ROOT / "images" / "login" / "later.png"        # optional

IMG_MENU         = ROOT / "images" / "main_10_default" / "menu.png"
IMG_LOGOUT       = ROOT / "images" / "main_10_default" / "logout.png"
IMG_LOGOUT_YES   = ROOT / "images" / "main_10_default" / "logout_yes.png"

LOADING_IMG      = ROOT / "images" / "ai_math" / "loading.png"

THRESHOLD  = 0.65
ROI_MARGIN = 20
POS_CACHE: dict[Path, tuple[int, int]] = {}

# ─────────── 헬퍼 함수들 ───────────
def wait_loading_gone(timeout: float = 15.0):
    def _visible():
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, 0.80) is not None
    adb_utils.wait_until(lambda: not _visible(), timeout, 0.7)

def _quick_verify(tpl: Path, scr_path: Path, pos) -> bool:
    import cv2
    tpl_img = cv2.imread(str(tpl)); scr_img = cv2.imread(str(scr_path))
    if tpl_img is None or scr_img is None: return False
    h, w = tpl_img.shape[:2]; cx, cy = pos
    y1 = max(cy-h//2-ROI_MARGIN,0); x1 = max(cx-w//2-ROI_MARGIN,0)
    y2 = min(cy+h//2+ROI_MARGIN, scr_img.shape[0])
    x2 = min(cx+w//2+ROI_MARGIN, scr_img.shape[1])
    roi = scr_img[y1:y2, x1:x2]
    if roi.size == 0: return False
    import cv2
    return cv2.minMaxLoc(
        cv2.matchTemplate(roi, tpl_img, cv2.TM_CCOEFF_NORMED)
    )[1] >= THRESHOLD

def tap_template(tpl: Path, timeout: float = 10.0):
    def _find_and_tap():
        scr = adb_utils.capture_screen()
        if tpl in POS_CACHE and _quick_verify(tpl, scr, POS_CACHE[tpl]):
            adb_utils.tap(*POS_CACHE[tpl]); return True
        pos = image_matcher.find_template_on_screen(tpl, scr, THRESHOLD)
        if pos:
            adb_utils.tap(*pos); POS_CACHE[tpl] = pos; return True
        return False
    if not adb_utils.wait_until(_find_and_tap, timeout, 0.5):
        raise RuntimeError(f"[탭 실패] {tpl}")

# ─────────── 단계 함수 ───────────
def do_login():
    tap_template(IMG_LOGIN_ID); time.sleep(0.3)
    adb_utils.input_text(USER_ID); time.sleep(0.2)

    tap_template(IMG_LOGIN_PW); time.sleep(0.3)
    adb_utils.input_text(USER_PW); time.sleep(0.2)

    tap_template(IMG_LOGIN_BTN); wait_loading_gone()

    try:
        tap_template(IMG_LOGIN_LATER, timeout=2.0); time.sleep(0.3)
    except RuntimeError:
        pass

def do_logout():
    tap_template(IMG_MENU);   time.sleep(0.4)
    tap_template(IMG_LOGOUT); time.sleep(0.3)
    tap_template(IMG_LOGOUT_YES); wait_loading_gone()

# ─────────── 메인 ───────────
if __name__ == "__main__":
    login_only = (len(sys.argv) > 1 and sys.argv[1] == "0")
    start_t = time.time()
    try:
        print(f"🚀  [{os.getenv('ADB_SERIAL','default')}] 로그인 시작")
        do_login()
        if not login_only:
            print("➡️  로그아웃 진행")
            do_logout()
        print(f"✅  완료! 소요 {time.time()-start_t:.2f}s")
    except Exception as e:
        print(f"❌  실패: {e} ({time.time()-start_t:.2f}s)")

