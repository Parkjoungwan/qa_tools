# tests/study_day_picker_fast.py
"""
요일별 학습 버튼 탐색 – 고속 버전
────────────────────────────────────────────────────────
● 요일 화면마다 adb screencap 을 1회만 수행
    ↳ ba / math / korean 의 study.png·resume.png를
      메모리-템플릿으로 일괄 매칭
● 금요일까지 못 찾으면 next_week 버튼 → 다음 주 월요일
● 최대 4주 반복 후에도 없으면 예외
"""

import os, time, cv2
from pathlib import Path
from dotenv import load_dotenv
from utils import adb_utils, image_matcher

# ───── .env 기기 지정 ──────────────────────────────────
load_dotenv()
_serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if _serial:
    adb_utils.set_device(_serial)
    print(f"📱  대상 기기: {_serial}")

# ───── 경로 및 우선순위 정의 ───────────────────────────
BASE = Path("images/main_10_default/study")
DAY_ORDER  = ["mon", "tue", "wes", "thu", "fri"]
SUBJECTS   = ["ba", "math", "korean"]
ACTIONS    = ["study", "resume"]

DAY_BTN = {d: BASE / f"{d}.png" for d in DAY_ORDER}
NEXT_WEEK = BASE / "next_week.png"
LOADING_IMG = Path("images/loading.png")

TH_BTN = 0.85
TH_LOAD = 0.65
TH_ACT = 0.80
MAX_WEEKS = 4

# ───── 템플릿 메모리 로드 (한 번만) ─────────────────────
TEMPLATES = []   # [(name, img_mat)]
for subj in SUBJECTS:
    for act in ACTIONS:
        p = BASE / subj / f"{act}.png"
        if p.exists():
            mat = cv2.imread(str(p), cv2.IMREAD_COLOR)
            if mat is not None:
                TEMPLATES.append((f"{subj}/{act}", mat, p))

# ───── 유틸 ────────────────────────────────────────────
def wait_loading_gone(timeout=25.0):
    def vis():
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, TH_LOAD) is not None
    adb_utils.wait_until(lambda: not vis(), timeout, 0.6)

def tap_image(img_path: Path, th=TH_BTN, timeout=10.0):
    return adb_utils.wait_until(
        lambda: (pos := image_matcher.find_template_on_screen(img_path,
                                                              adb_utils.capture_screen(),
                                                              th)) and (adb_utils.tap(*pos) or True),
        timeout, 0.7)

def find_any_template(scr_path: Path):
    scr = cv2.imread(str(scr_path), cv2.IMREAD_COLOR)
    if scr is None:
        return None
    # h_scr, w_scr = scr.shape[:2]   # ← 더 이상 크기 check 하지 않음

    for name, tpl, path in TEMPLATES:
        res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= TH_ACT:
            h, w = tpl.shape[:2]
            x, y = max_loc[0] + w // 2, max_loc[1] + h // 2
            return name, (x, y)
    return None

# ───── 메인 루프 ───────────────────────────────────────
def run():
    week = day_idx = 0
    while week < MAX_WEEKS:
        day = DAY_ORDER[day_idx]
        if week or day_idx:                    # 첫 월요일은 클릭 생략
            print(f"➡️  {day} 버튼 탭")
            tap_image(DAY_BTN[day])
            wait_loading_gone()

        print(f"🔍  {day} 화면 캡처 & 템플릿 탐색")
        scr = adb_utils.capture_screen()       # ← 1회만 캡처
        hit = find_any_template(scr)
        if hit:
            name, pos = hit
            print(f"✅  {name} 찾음 → 탭 후 종료")
            adb_utils.tap(*pos)
            return

        # 다음 요일 or 다음 주
        if day_idx < 4:
            day_idx += 1
        else:
            print("➜  next_week 버튼 탭")
            tap_image(NEXT_WEEK)
            wait_loading_gone()
            week += 1
            day_idx = 0
    raise RuntimeError("4주 동안 대상 버튼을 찾지 못했습니다.")

# ───── 실행부 ──────────────────────────────────────────
if __name__ == "__main__":
    t0 = time.time()
    try:
        run()
        print(f"\n🎉 완료! 소요 {time.time()-t0:.2f}s")
    except Exception as e:
        print(f"\n❌ 실패: {e} ({time.time()-t0:.2f}s)")

