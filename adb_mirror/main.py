import sys, argparse, time, subprocess, threading
from datetime import datetime
from pathlib import Path
from typing import List

from controllers.android import AndroidController, get_android_devices
from controllers.ios import IOSController, get_ios_devices
from controllers.base import DeviceController

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

    # --- Device Detection ---
    controllers: List[DeviceController] = []
    android_serials = get_android_devices()
    controllers.extend([AndroidController(s) for s in android_serials])

    ios_serials = get_ios_devices()
    controllers.extend([IOSController(s) for s in ios_serials])

    if not controllers:
        print("⛔ No devices found."); sys.exit(1)
    
    if args.flip:
        controllers.reverse()
    
    print(f"Found {len(controllers)} device(s).")
    for c in controllers:
        res_str = f"{c.device_res[0]}x{c.device_res[1]}" if c.device_res else "Unknown Res"
        type_str = "Android" if isinstance(c, AndroidController) else "iOS"
        print(f"🎮 Using {type_str} device: {c.serial} ({res_str})")


    # --- Window and Mirroring Setup ---
    VIEW_W = 1200
    VIEW_H = 750

    for i, controller in enumerate(controllers):
        rect = (i * VIEW_W, 0, VIEW_W, VIEW_H)
        no_control = (args.mode == 'log')
        p = controller.start_mirror(f"Mirror - {controller.serial}", rect, no_control=no_control)
        if p:
            # Start a thread to print stderr for debugging
            threading.Thread(target=lambda: [print(f"[{controller.serial}] {l.decode().strip()}") for l in iter(p.stderr.readline, b'')], daemon=True).start()

    # --- Mode Handling ---
    if args.mode == 'fast':
        print("\n✅ Mirroring windows launched in FAST mode. Waiting for exit...")
        # In fast mode, we just wait for the processes to end.
        for controller in controllers:
            if controller.mirror_process:
                controller.mirror_process.wait()

    else: # args.mode == 'log'
        from PyQt5.QtWidgets import QApplication
        from viewer import MultiViewer

        app = QApplication(sys.argv)

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

        viewer = MultiViewer(controllers, log_fn=log_event,
                             viewer_width_per_device=VIEW_W, viewer_height=VIEW_H)
        viewer.show()
        app.exec_()
        
        log_fp.close()
        print("📄 Log saved:", log_path)

    # --- Cleanup ---
    print("Cleaning up resources...")
    for controller in controllers:
        controller.stop_mirror()
    print("✨ All mirror windows closed.")

if __name__=="__main__":
    main()