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

from PyQt5.QtWidgets import QApplication

# ───────────────────── 연결 기기 탐색 ─────────────────────
def pick_devices(max_devices: int = 2) -> List[str]:
    lines = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
    return [l.split()[0] for l in lines if l.strip().endswith("device")][:max_devices]

# ─────────────────────────── main ───────────────────────────
def main() -> None:
    app = QApplication(sys.argv)

    ap = argparse.ArgumentParser()
    ap.add_argument("--flip", action="store_true",
                    help="swap left/right device order on viewer")
    args = ap.parse_args()

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

    # ── 창 크기: 960×600 (1920×1200의 ½) ────────────────────
    VIEW_W = 1200
    VIEW_H = 750
    SCRCPY_MAX = "960"

    # ── scrcpy 실행 ─────────────────────────────────────────
    scrcpy_ps = []
    for i, s in enumerate(serials):
        cmd = [
            "scrcpy","--serial",s,"--no-control","--no-audio",
            "--window-title",f"scrcpy - {s}",
            "--window-x",str(i*VIEW_W),"--window-y","0",
            "--window-width",str(VIEW_W),"--window-height",str(VIEW_H),
            "--window-borderless","--max-size",SCRCPY_MAX,
        ]
        p = subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        scrcpy_ps.append(p)
        threading.Thread(target=lambda pr,sid=s:[print(f"[{sid}] {l.decode().strip()}")
                         for l in iter(pr.stderr.readline,b'')],daemon=True,args=(p,)).start()
        time.sleep(1)

    # ── 실시간 로그 파일 ───────────────────────────────────
    log_dir = Path(__file__).with_name("log"); log_dir.mkdir(exist_ok=True)
    log_path = log_dir/f"adb_{datetime.now():%Y%m%d_%H%M%S}.log"
    log_fp   = log_path.open("w",encoding="utf-8",buffering=1)
    log_fp.write("type\telapsed\tserial\ttext\tx1\ty1\tx2\ty2\tduration\n")

    # ── 뷰어 초기화 ────────────────────────────────────────
    from viewer import MultiViewer, tap, swipe, text
    start_t = time.perf_counter()

    def log_event(kind, serial, *a):
        dt = time.perf_counter()-start_t
        if kind=="tap":
            x,y=a; line=f"tap\t{dt:.2f}\t{serial}\t\t{x}\t{y}"
        elif kind=="swipe":
            sx,sy,ex,ey,d=a; line=f"swipe\t{dt:.2f}\t{serial}\t\t{sx}\t{sy}\t{ex}\t{ey}\t{d}"
        elif kind=="text":
            text_to_input,=a; line=f"text\t{dt:.2f}\t{serial}\t{text_to_input}"
        elif kind=="cap":
            line=f"cap\t{dt:.2f}\t{serial}"
        else: return
        print(line); log_fp.write(line+"\n")

    viewer = MultiViewer(serials, log_fn=log_event,
                         device_resolutions=device_res,
                         viewer_width_per_device=VIEW_W,
                         viewer_height=VIEW_H)

    viewer.tap_func   = lambda s,x,y,v=viewer: threading.Thread(
        target=tap,args=(s,x,y,v),daemon=True).start()
    viewer.swipe_func = lambda s,x1,y1,x2,y2,d,v=viewer: threading.Thread(
        target=swipe,args=(s,x1,y1,x2,y2,d,v),daemon=True).start()
    viewer.text_func = lambda s, t, v=viewer: threading.Thread(
        target=text, args=(s, t, v), daemon=True).start()

    viewer.show()
    try: sys.exit(app.exec_())
    finally:
        for p in scrcpy_ps: p.terminate(); p.wait()
        log_fp.close(); print("📄 Log saved:", log_path)

if __name__=="__main__":
    main()


