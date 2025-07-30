#!/usr/bin/env python3
# utils/touch_coord_logger.py
import os, re, shlex, subprocess, sys, select, termios, tty, argparse
from dotenv import load_dotenv

# ── ADB prefix ─────────────────────────────────────────
load_dotenv()
SERIAL = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
ADB = ["adb", "-s", SERIAL] if SERIAL else ["adb"]

def adb(cmd: str) -> str:
    return subprocess.check_output([*ADB, *shlex.split(cmd)], text=True).strip()

def adb_stream(cmd: str):
    return subprocess.Popen([*ADB, *shlex.split(cmd)],
                            stdout=subprocess.PIPE, text=True)

# ── 모든 input 디바이스 파싱 ───────────────────────────
def parse_input_devices() -> dict[str, set[str]]:
    """
    { "/dev/input/event3": {"ABS_MT_POSITION_X", "ABS_MT_POSITION_Y", …}, … }
    """
    dev_caps: dict[str, set[str]] = {}
    dev = None
    for line in adb("shell getevent -lp").splitlines():
        m = re.search(r"(/dev/input/event\d+)", line)
        if m:
            dev = m.group(1)
            dev_caps[dev] = set()
            continue
        if dev:
            cap = re.search(r"^\s*([A-Z0-9_]+)", line)
            if cap:
                dev_caps[dev].add(cap.group(1))
    return dev_caps

def select_touch_device(dev_caps: dict[str, set[str]]) -> str | None:
    # 우선순위: ABS_MT_* 모두 → ABS_X & ABS_Y
    for dev, caps in dev_caps.items():
        if {"ABS_MT_POSITION_X", "ABS_MT_POSITION_Y"} <= caps:
            return dev
    for dev, caps in dev_caps.items():
        if {"ABS_X", "ABS_Y"} <= caps:
            return dev
    return None

# ── 좌표 모니터 ────────────────────────────────────────
def monitor(device: str, caps: set[str]):
    mt = "ABS_MT_POSITION_X" in caps
    print(f"\n📡  터치 좌표 수신 중… (q 키 종료)\n    device: {device}\n")
    proc = adb_stream(f"shell getevent -lt {device}")

    get_val = lambda l, key: int(l.split()[-1], 16) if key in l else None
    x = y = None
    stdin_fd = sys.stdin.fileno()
    old = termios.tcgetattr(stdin_fd); tty.setcbreak(stdin_fd)
    try:
        while True:
            # quit
            if select.select([sys.stdin], [], [], 0)[0] and sys.stdin.read(1) == "q":
                break
            line = proc.stdout.readline()
            if not line: break
            if (vx := get_val(line, "POSITION_X" if mt else "ABS_X")) is not None:
                x = vx
            elif (vy := get_val(line, "POSITION_Y" if mt else "ABS_Y")) is not None:
                y = vy
            elif "SYN_REPORT" in line and x is not None and y is not None:
                print(f"👉 ({x}, {y})")
                x = y = None
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old); proc.terminate()

# ── CLI ───────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Show touch coordinates live.")
    ap.add_argument("--list", action="store_true", help="디바이스 목록만 출력")
    ap.add_argument("--device", help="/dev/input/eventN 직접 지정")
    args = ap.parse_args()

    caps_map = parse_input_devices()
    if args.list:
        print("input devices & caps:")
        for d, c in caps_map.items(): print(f"{d}: {', '.join(sorted(c))}")
        sys.exit(0)

    dev = args.device or select_touch_device(caps_map)
    if not dev:
        print("❌  터치스크린 input 노드를 찾지 못했습니다.\n"
              "   ‣ adb shell getevent -lp 로 직접 확인 후 --device 옵션 사용")
        sys.exit(1)

    print(f"📱  ADB target: {SERIAL or '(default)'}")
    monitor(dev, caps_map[dev])

