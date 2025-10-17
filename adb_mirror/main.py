import sys, os, argparse, time, subprocess, threading
from datetime import datetime
from pathlib import Path
from typing import List

# ── venv site‑packages 경로 주입 ─────────────────────────────
site_packages_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "venv", "lib", "python3.13", "site-packages"
)
if site_packages_path not in sys.path:
    sys.path.insert(0, site_packages_path)

# ───────────────────── 연결 기기 탐색 ─────────────────────
def pick_devices(max_devices: int = 2) -> List[str]:
    lines = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
    return [l.split()[0] for l in lines if l.strip().endswith("device")][:max_devices]

# ─────────────────────────── main ───────────────────────────
def main() -> None:
    # ADB 서버를 재시작하여 모든 기존 연결/포워딩/좀비 프로세스를 초기화
    print("🔄 Restarting ADB server for a clean state...")
    subprocess.run(["adb", "kill-server"], capture_output=True)
    subprocess.run(["adb", "start-server"], capture_output=True)

    ap = argparse.ArgumentParser()
    ap.add_argument("--flip", action="store_true", help="swap left/right device order")
    ap.add_argument("--mode", choices=['fast', 'log'], default='fast',
                    help="Input mode: 'fast' for low-latency (no logging), 'log' for high-latency (with logging)")
    args = ap.parse_args()

    print(f"🚀 Starting in {args.mode.upper()} mode.")

    serials = pick_devices(2)
    if not serials:
        print("⛔ ADB 기기가 연결되지 않았습니다."); sys.exit(1)
    print(f"Found {len(serials)} device(s).")
    if args.flip:
        serials.reverse()
    print("🎮 Using devices:", serials)

    # ── 디바이스 해상도 (세로/가로 스왑) ─────────────────────
    device_res = {}
    for s in serials:
        w, h = map(int, subprocess.check_output(
            ["adb","-s",s,"shell","wm","size"]).decode().strip().split(": ")[-1].split("x"))
        if h > w: w, h = h, w
        device_res[s] = (w, h)
        print(f"{s}: {w}×{h}")

    # ── 창 크기 ────────────────────────────────────────────
    VIEW_W = 1200
    VIEW_H = 750
    SCRCPY_MAX = "960"

    # ── scrcpy 공통 옵션 ───────────────────────────────────
    scrcpy_common_args = [
        "--no-audio",
        "--window-borderless",
        "--max-size", SCRCPY_MAX,
    ]

    # ── 모드에 따른 scrcpy 실행 및 대기 ───────────────────
    scrcpy_ps = []
    if args.mode == 'fast':
        # FAST MODE: scrcpy가 직접 제어. 가장 단순한 형태로 실행.
        for i, s in enumerate(serials):
            cmd = ["scrcpy", "--serial", s] + scrcpy_common_args + [
                "--window-title", f"scrcpy - {s}",
                "--window-x", str(i * VIEW_W), "--window-y", "0",
                "--window-width", str(VIEW_W), "--window-height", str(VIEW_H),
            ]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            scrcpy_ps.append(p)
            # 실시간 에러 출력을 위한 스레드는 그대로 유지
            threading.Thread(target=lambda pr, sid=s: [print(f"[{sid}] {l.decode().strip()}") for l in iter(pr.stderr.readline, b'')], daemon=True, args=(p,)).start()

        print("\n✅ scrcpy windows launched in FAST mode. Waiting for exit...")

        # --- 프로세스 종료 후 결과 및 오류를 명시적으로 출력 (디버깅용) ---
        for p in scrcpy_ps:
            stdout, stderr = p.communicate() # 프로세스가 종료될 때까지 기다리고 출력을 가져옴
            if p.returncode != 0:
                # p.args에서 시리얼 번호 추출 (cmd 리스트의 3번째 요소)
                serial = p.args[2] if len(p.args) > 2 else "unknown"
                print(f"🚨 scrcpy process for device {serial} exited with error code {p.returncode}.")
                if stdout:
                    print(f"   --- stdout ---\n{stdout.decode('utf-8', errors='ignore')}")
                if stderr:
                    print("   --- stderr ---")
                    print(stderr.decode('utf-8', errors='ignore'))


    else: # args.mode == 'log'
        # LOG MODE: viewer.py 오버레이로 제어 및 로깅.
        from PyQt5.QtWidgets import QApplication
        app = QApplication(sys.argv)
        from viewer import MultiViewer, tap, swipe, text

        for i, s in enumerate(serials):
            cmd = ["scrcpy", "--serial", s, "--no-control"] + scrcpy_common_args + [
                "--window-title", f"scrcpy - {s}",
                "--window-x", str(i * VIEW_W), "--window-y", "0",
                "--window-width", str(VIEW_W), "--window-height", str(VIEW_H),
            ]
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
            scrcpy_ps.append(p)
            threading.Thread(target=lambda pr, sid=s: [print(f"[{sid}] {l.decode().strip()}") for l in iter(pr.stderr.readline, b'')], daemon=True, args=(p,)).start()
            time.sleep(1)

        log_dir = Path(__file__).with_name("log"); log_dir.mkdir(exist_ok=True)
        log_path = log_dir/f"adb_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_fp = log_path.open("w", encoding="utf-8", buffering=1)
        log_fp.write("type\telapsed\tserial\ttext\tx1\ty1\tx2\ty2\tduration\n")
        start_t = time.perf_counter()

        def log_event(kind, serial, *a):
            dt = time.perf_counter() - start_t
            line = f"{kind}\t{dt:.2f}\t{serial}"
            if kind == "tap": line += f"\t\t{a[0]}\t{a[1]}"
            elif kind == "swipe": line += f"\t\t{a[0]}\t{a[1]}\t{a[2]}\t{a[3]}\t{a[4]}"
            elif kind == "text": line += f"\t{a[0]}"
            print(line); log_fp.write(line + "\n")

        viewer = MultiViewer(serials, log_fn=log_event, device_resolutions=device_res,
                             viewer_width_per_device=VIEW_W, viewer_height=VIEW_H)
        viewer.tap_func = lambda s, x, y, v=viewer: threading.Thread(target=tap, args=(s, x, y, v), daemon=True).start()
        viewer.swipe_func = lambda s, x1, y1, x2, y2, d, v=viewer: threading.Thread(target=swipe, args=(s, x1, y1, x2, y2, d, v), daemon=True).start()
        viewer.text_func = lambda s, t, v=viewer: threading.Thread(target=text, args=(s, t, v), daemon=True).start()
        viewer.show()
        app.exec_()
        # app.exec_() is blocking, code below will run after viewer is closed
        log_fp.close(); print("📄 Log saved:", log_path)

    # --- Cleanup ---
    try:
        # Wait for all scrcpy processes to complete (if they haven't already)
        for p in scrcpy_ps:
            p.wait(timeout=1)
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        pass # Ignore timeout, just proceed to terminate
    finally:
        for p in scrcpy_ps:
            if p.poll() is None:
                p.terminate()
                p.wait()
        print("✨ All scrcpy windows closed.")

if __name__=="__main__":
    main()