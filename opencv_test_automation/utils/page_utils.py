# utils/page_utils.py
"""
페이지(Navi Bar) 인식 유틸
────────────────────────────────────────────
`detect_current_page()`를 호출하면
    ("ai_math", 0.92)  처럼 (폴더명, score) 를 반환하거나
    (None, score)      ← 임계값 미달
"""

from pathlib import Path
from typing import Tuple, Optional
import cv2, numpy as np

from opencv_test_automation.utils import adb_utils

# ROOT 정의 추가
ROOT = Path(__file__).resolve().parent.parent

# 지원 페이지 폴더 & 템플릿 파일 이름
PAGES = [
    "main_10_default",
    "subject_study",
    "unit_master",
    "ai_math",
    "ai_exam",
    "knowledge_land",
    "ai_report",
]
TEMPLATES = {p: ROOT / "images" / p / "navi_origin.png" for p in PAGES}
THRESHOLD = 0.80     # 최소 매칭 스코어
ROI_MARGIN = 20      # fast re-verify 용 (POS_CACHE 재활용)
POS_CACHE = {}

def _match_score(tpl_path: Path, scr_path: Path) -> float:
    tpl, scr = cv2.imread(str(tpl_path)), cv2.imread(str(scr_path))
    if tpl is None or scr is None: return 0.0
    if scr.shape[0] < tpl.shape[0] or scr.shape[1] < tpl.shape[1]:
        return 0.0
    res = cv2.matchTemplate(scr, tpl, cv2.TM_CCOEFF_NORMED)
    return cv2.minMaxLoc(res)[1]

def detect_current_page() -> Tuple[Optional[str], float]:
    """현재 화면을 캡처해 가장 높은 페이지/스코어를 반환."""
    scr_path = adb_utils.capture_screen()
    best_page, best = None, 0.0
    for page, tpl in TEMPLATES.items():
        score = _match_score(tpl, scr_path)
        if score > best:
            best_page, best = page, score
    if best >= THRESHOLD:
        return best_page, best
    return None, best

