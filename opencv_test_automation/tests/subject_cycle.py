# tests/subject_cycle.py
"""
과목별 체크-→강제체크-→다음 버튼 순차 탭

사용 예
──────
python -m tests.subject_cycle math 3      # math 폴더에서 3회
python -m tests.subject_cycle korean 1    # korean 폴더 1회(기본)

폴더 구조
images/main_10_default/study/<subject>/
 ├─ check.png
 ├─ force_check.png
 └─ next.png
"""

import os, time, argparse
from pathlib import Path
from dotenv import load_dotenv
from utils import adb_utils, image_matcher

# ─────── .env 기기 지정 ────────────────────────────────
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")

# ─────── 공통 설정 ─────────────────────────────────────
BASE = Path("images/main_10_default/study")
LOADING_IMG = Path("images/loading.png")
TH_IMG   = 0.85
TH_LOAD  = 0.65

def tap_image(img: Path, th=TH_IMG, timeout=12):
    def _tap():
        scr = adb_utils.capture_screen()
        pos = image_matcher.find_template_on_screen(img, scr, th)
        if pos:
            adb_utils.tap(*pos); return True
        return False
    return adb_utils.wait_until(_tap, timeout, 0.7)

def wait_loading():
    def vis():
        scr = adb_utils.capture_screen()
        return image_matcher.find_template_on_screen(LOADING_IMG, scr, TH_LOAD) is not None
    adb_utils.wait_until(lambda: not vis(), 30, 0.6)

# ─────── 메인 루틴 ─────────────────────────────────────
def run(subject: str, times: int):
    folder = BASE / subject
    if not (folder / "check.png").exists():
        raise FileNotFoundError(f"{folder} 폴더가 존재하지 않거나 PNG가 없습니다.")

    check_img  = folder / "check.png"
    force_img  = folder / "force_check.png"
    next_img   = folder / "next.png"

    for n in range(1, times + 1):
        print(f"\n🔄 사이클 {n}/{times}")
        for name, img in [("check", check_img), ("force_check", force_img), ("next", next_img)]:
            print(f"   ▶ {name} 탭")
            if not tap_image(img):
                raise RuntimeError(f"{name} 버튼을 찾지 못했습니다. ({img})")
            wait_loading()

    print("\n✅ 모든 사이클 완료")

# ─────── CLI ───────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("subject", choices=["math", "korean", "ba"],
                    help="과목 폴더 이름")
    ap.add_argument("count", nargs="?", type=int, default=1,
                    help="반복 횟수 (기본 1)")
    args = ap.parse_args()

    start = time.time()
    try:
        run(args.subject, args.count)
        print(f"총 소요: {time.time()-start:.2f}s")
    except Exception as e:
        print(f"❌ 실패: {e} ({time.time()-start:.2f}s)")

