# tests/month_report_test.py
"""
AI Report 월간 리포트 자동화
────────────────────────────────────────────────────────
1. main_10_default/ai_report 이미지를 터치해 AI 리포트 화면 진입
2. loading.png 이 사라질 때까지 대기
3. 아래 순서대로 이미지 터치
     (※ year/month 토글류 4개는 중심에서 Y −20 픽셀 오프셋)
       ┌ year_toggle_from   ★ offset
       ├ year_2024_from
       ├ month_toggle_from  ★ offset
       ├ month_1_from
       ├ year_toggle_to     ★ offset
       ├ year_2024_to
       ├ month_toggle_to    ★ offset
       ├ month_3_to
       └ search
4. 모든 단계 완료 후 main_10 이미지를 터치하고 종료
"""

import os, time
from pathlib import Path
from dotenv import load_dotenv
from utils import adb_utils, image_matcher

# ─── .env 로드 & 기기 지정 ─────────────────────────────────
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")
else:
    print("⚠️  ADB_SERIAL이 정의되지 않았습니다. 단일 기기만 연결되어 있어야 합니다.")

# ─── 템플릿 경로 ─────────────────────────────────────────
MAIN_AI_REPORT = Path("images/main_10_default/ai_report.png")
LOADING_IMG    = Path("images/ai_report/loading.png")

SEQ = [
    Path("images/ai_report/year_toggle_from.png"),
    Path("images/ai_report/year_2024_from.png"),
    Path("images/ai_report/month_toggle_from.png"),
    Path("images/ai_report/month_1_from.png"),
    Path("images/ai_report/year_toggle_to.png"),
    Path("images/ai_report/year_2024_to.png"),
    Path("images/ai_report/month_toggle_to.png"),
    Path("images/ai_report/month_3_to.png"),
    Path("images/ai_report/search.png"),
]

MAIN_RETURN = Path("images/ai_report/main_10.png")

# 토글 4개는 오프셋 −20 픽셀 ↑
OFFSET_TPLS = {
    "year_toggle_from.png",
    "month_toggle_from.png",
    "year_toggle_to.png",
    "month_toggle_to.png",
}
Y_OFFSET = -20
THRESHOLD = 0.85
ROI_MARGIN = 20
POS_CACHE: dict[Path, tuple[int, int]] = {}

# ─── 헬퍼 ────────────────────────────────────────────────
def wait_loading_gone(timeout=15.0):
    def _visible():
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, 0.80) is not None
    adb_utils.wait_until(lambda: not _visible(), timeout, 0.7)

def _quick_verify(tpl: Path, scr: Path, pos) -> bool:
    import cv2
    tpl_img = cv2.imread(str(tpl)); scr_img = cv2.imread(str(scr))
    if tpl_img is None or scr_img is None: return False
    h, w = tpl_img.shape[:2]; cx, cy = pos
    y1 = max(cy-h//2-ROI_MARGIN,0); x1=max(cx-w//2-ROI_MARGIN,0)
    y2 = min(cy+h//2+ROI_MARGIN, scr_img.shape[0])
    x2 = min(cx+w//2+ROI_MARGIN, scr_img.shape[1])
    roi = scr_img[y1:y2, x1:x2]
    if roi.size ==0: return False
    import cv2
    return cv2.minMaxLoc(cv2.matchTemplate(roi,tpl_img,cv2.TM_CCOEFF_NORMED))[1] >= THRESHOLD

def tap_template(tpl: Path, timeout=10.0):
    def _find_and_tap():
        scr = adb_utils.capture_screen()
        if tpl in POS_CACHE and _quick_verify(tpl, scr, POS_CACHE[tpl]):
            x, y = POS_CACHE[tpl]
        else:
            pos = image_matcher.find_template_on_screen(tpl, scr, THRESHOLD)
            if not pos: return False
            POS_CACHE[tpl] = pos
            x, y = pos
        # 오프셋 적용 여부
        if tpl.name in OFFSET_TPLS:
            y += Y_OFFSET
        adb_utils.tap(x, y)
        return True
    if not adb_utils.wait_until(_find_and_tap, timeout, 0.5):
        raise RuntimeError(f"[탭 실패] {tpl}")

# ─── 메인 로직 ───────────────────────────────────────────
def run_month_report():
    tap_template(MAIN_AI_REPORT)
    wait_loading_gone()

    for tpl in SEQ:
        tap_template(tpl)
        time.sleep(0.4)
        wait_loading_gone()

    tap_template(MAIN_RETURN)

# ─── 실행부 ──────────────────────────────────────────────
if __name__ == "__main__":
    start = time.time()
    try:
        print("🚀  월간 리포트 자동화 시작")
        run_month_report()
        print(f"✅  완료! 소요 {time.time()-start:.2f}s")
    except Exception as e:
        print(f"❌  실패: {e} ({time.time()-start:.2f}s)")

