import subprocess
import re
import os
import time
import logging
from typing import List, Optional, Tuple
import numpy as np
import cv2
from datetime import datetime
import uiautomator2 as u2

logger = logging.getLogger(__name__)

def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def get_device_serials() -> List[str]:
    serial = os.getenv("DEVICE_SERIAL")
    if serial:
        return [serial]
    lines = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
    return [l.split()[0] for l in lines if l.strip().endswith("device")]

def get_device_property(serial: str, prop: str) -> str:
    try:
        return subprocess.check_output(["adb", "-s", serial, "shell", "getprop", prop]).decode().strip()
    except Exception:
        return ""

def get_device_resolution(serial: str) -> Optional[Tuple[int, int]]:
    try:
        output = subprocess.check_output(["adb", "-s", serial, "shell", "wm", "size"]).decode()
        match = re.search(r'(\d+)x(\d+)', output)
        if match:
            return int(match.group(1)), int(match.group(2))
    except Exception as e:
        logger.error(f"Error getting device resolution: {e}")
    return None

def get_device_orientation(serial: str) -> int:
    try:
        output = subprocess.check_output(
            ["adb", "-s", serial, "shell", "dumpsys", "input"], 
            stderr=subprocess.PIPE
        ).decode()
        match = re.search(r'SurfaceOrientation:\s*(\d+)', output)
        if match:
            return int(match.group(1))
    except Exception as e:
        logger.warning(f"Could not get device orientation: {e}. Assuming 0 (portrait).")
    return 0

def get_stable_insets(serial: str) -> Tuple[int, int, int, int]:
    try:
        output = subprocess.check_output(
            ["adb", "-s", serial, "shell", "dumpsys", "window"], 
            stderr=subprocess.PIPE
        ).decode()
        match = re.search(r'(?:mStable|mStableInsets)=\[(\d+),(\d+),(\d+),(\d+)\]', output)
        if match:
            return int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
    except Exception as e:
        logger.warning(f"Could not get stable insets: {e}. Assuming no insets.")
    return 0, 0, 0, 0

def set_developer_option(serial: str, key: str, value: int):
    try:
        subprocess.run(["adb", "-s", serial, "shell", "settings", "put", "system", key, str(value)], check=True, capture_output=True)
        logger.info(f"Set developer option '{key}' to {value}")
    except Exception as e:
        logger.warning(f"Failed to set developer option '{key}': {e}. This may require extra permissions.")

def adb_tap(serial: str, x: int, y: int):
    subprocess.run(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)])

def adb_swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration: int):
    subprocess.run(["adb", "-s", serial, "shell", "input", "swipe",
                    str(x1), str(y1), str(x2), str(y2), str(duration)])

def adb_capture(serial: str, max_retries=3) -> Optional[np.ndarray]:
    last_exception = None
    for attempt in range(max_retries):
        try:
            proc = subprocess.run(
                ["adb", "-s", serial, "exec-out", "screencap", "-p"],
                capture_output=True, check=True, timeout=10
            )
            image_data = np.frombuffer(proc.stdout, np.uint8)
            if image_data.tobytes().startswith(b'\r\n'):
                image_data = image_data[2:]
            img = cv2.imdecode(image_data, cv2.IMREAD_COLOR)
            if img is not None:
                return img
            else:
                last_exception = ValueError("cv2.imdecode returned None")
        except Exception as e:
            last_exception = e
            logger.warning(f"adb_capture attempt {attempt + 1}/{max_retries} failed: {e}")
        
        if attempt < max_retries - 1:
            wait_time = 0.1 * (2 ** attempt) 
            time.sleep(wait_time)

    logger.error(f"adb_capture failed after {max_retries} attempts. Last error: {last_exception}")
    return None

def connect_uiautomator(serial: str) -> Optional[u2.Device]:
    try:
        d = u2.connect(serial)
        logger.info(f"Successfully connected to uiautomator2 on {serial}")
        return d
    except Exception as e:
        logger.error(f"Failed to connect to uiautomator2 on {serial}: {e}")
        return None
