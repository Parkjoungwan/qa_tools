from pathlib import Path
import cv2


def find_template_on_screen(template_path: Path,
                            screen_path: Path,
                            threshold: float = 0.85):
    """
    템플릿을 화면에서 찾아 중심 좌표 (x, y) 반환.
    일치율이 threshold 미만이면 None.
    """
    screen = cv2.imread(str(screen_path))
    template = cv2.imread(str(template_path))

    if screen is None or template is None:
        raise FileNotFoundError("이미지를 읽을 수 없습니다.")

    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return None

    h, w = template.shape[:2]
    cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
    return (cx, cy)

