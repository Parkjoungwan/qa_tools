"""
ADB 유틸리티 (멀티-디바이스 대응)
────────────────────────────────
• _SERIAL 은 ① ADB_SERIAL ② ANDROID_SERIAL 순으로 검사
• 명령 행마다 자동으로 “adb -s <serial> …”  접두어 부착
"""
import os, subprocess, time, shlex
from pathlib import Path

# ── ❶ 직렬번호 탐색 ──────────────────────────────
_SERIAL: str | None = (
    os.getenv("ADB_SERIAL") or      # 사용자 지정
    os.getenv("ANDROID_SERIAL")     # adb 표준 변수
)

def set_device(serial: str | None):
    """런타임에 직렬번호를 바꿀 수 있다(None=해제)."""
    global _SERIAL
    _SERIAL = serial

def _adb_prefix() -> str:
    return f"adb -s {_SERIAL}" if _SERIAL else "adb"

# ── (나머지 함수는 동일) ─────────────────────────
_TMP_REMOTE = "/sdcard/__cap.png"
_TMP_LOCAL  = Path("./.tmp_screen.png")

def _run(cmd: str) -> str:
    return subprocess.check_output(cmd, shell=True, text=True).strip()

def capture_screen() -> Path:
    _run(f"{_adb_prefix()} shell screencap -p {_TMP_REMOTE}")
    _run(f"{_adb_prefix()} pull {_TMP_REMOTE} {_TMP_LOCAL}")
    _run(f"{_adb_prefix()} shell rm {_TMP_REMOTE}")
    return _TMP_LOCAL

def tap(x: int, y: int):
    _run(f"{_adb_prefix()} shell input tap {x} {y}")

def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
    _run(f"{_adb_prefix()} shell input swipe {x1} {y1} {x2} {y2} {duration_ms}")

def input_text(text: str):
    esc = (
        text.replace("\\", "\\\\").replace("\"","\\\"")
            .replace("$","\\$").replace(" ", "%s")
    )
    _run(f"{_adb_prefix()} shell input text {shlex.quote(esc)}")

def wait_until(fn, timeout: float = 10.0, interval: float = 0.5) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if fn(): return True
        time.sleep(interval)
    return False

