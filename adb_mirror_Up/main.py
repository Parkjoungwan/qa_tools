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

    # ── 로그, 샘플, 지문 디렉토리 ────────────────────────────
    log_dir = Path(__file__).with_name("log"); log_dir.mkdir(exist_ok=True)
    samples_dir = Path(__file__).with_name("samples"); samples_dir.mkdir(exist_ok=True)
    fingerprints_dir = Path(__file__).with_name("page_fingerprints"); fingerprints_dir.mkdir(exist_ok=True)
    (fingerprints_dir / 'pagination').mkdir(exist_ok=True)

    log_path = log_dir/f"adb_{datetime.now():%Y%m%d_%H%M%S}.log"
    log_fp   = log_path.open("w",encoding="utf-8",buffering=1)
    log_fp.write("type\telapsed\tserial\tpage\ttext\tx1\ty1\tx2\\y2\tduration\n")


    # ── 뷰어 초기화 ────────────────────────────────────────
    from viewer import MultiViewer, tap, swipe, text, capture_sample, handle_page_recognition
    start_t = time.perf_counter()

    log_fp = [None] # Use a list to make it mutable inside the closure
    def open_new_log():
        if log_fp[0]:
            log_fp[0].close()
        log_path = log_dir/f"adb_{datetime.now():%Y%m%d_%H%M%S}.log"
        log_fp[0] = log_path.open("w",encoding="utf-8",buffering=1)
        log_fp[0].write("type\telapsed\tserial\tpage\ttext\tx1\ty1\tx2\\y2\tduration\n")
        print(f"📄 New log file started: {log_path.name}")
    
    open_new_log()

    def log_event(kind, serial, *a):
        dt = time.perf_counter()-start_t
        page = viewer.current_page_name
        if kind=="tap":
            x,y=a; line=f"tap\t{dt:.2f}\t{serial}\t{page}\t\t{x}\t{y}"
        elif kind=="swipe":
            sx,sy,ex,ey,d=a; line=f"swipe\t{dt:.2f}\t{serial}\t{page}\t\t{sx}\t{sy}\t{ex}\t{ey}\t{d}"
        elif kind=="text":
            text_to_input,=a; line=f"text\t{dt:.2f}\t{serial}\t{page}\t{text_to_input}"
        elif kind=="cap":
            line=f"cap\t{dt:.2f}\t{serial}\t{page}"
        else: return
        print(line); log_fp[0].write(line+"\n")

    def save_and_reset_log():
        print("\n🔄 Saving current log and generating new graph data...")
        log_fp[0].close()
        
        try:
            subprocess.run(["python3", "generate_graph_data.py"], check=True)
            print("✅ Graph data regenerated.")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ Failed to generate graph data: {e}")

        open_new_log()
        print("Ready for new logging session.")

    viewer = MultiViewer(serials, log_fn=log_event,
                         device_resolutions=device_res,
                         viewer_width_per_device=VIEW_W,
                         viewer_height=VIEW_H,
                         samples_dir=samples_dir,
                         fingerprints_dir=fingerprints_dir)

    viewer.tap_func   = lambda s,x,y,v=viewer: threading.Thread(
        target=tap,args=(s,x,y,v),daemon=True).start()
    viewer.swipe_func = lambda s,x1,y1,x2,y2,d,v=viewer: threading.Thread(
        target=swipe,args=(s,x1,y1,x2,y2,d,v),daemon=True).start()
    viewer.text_func = lambda s, t, v=viewer: threading.Thread(
        target=text, args=(s, t, v), daemon=True).start()
    viewer.capture_func = lambda s,x,y,v=viewer: threading.Thread(
        target=capture_sample,args=(s,x,y,v),daemon=True).start()
    viewer.page_rec_func = lambda v=viewer: threading.Thread(
        target=handle_page_recognition,args=(v,),daemon=True).start()
    viewer.save_log_func = save_and_reset_log
    viewer.scan_pagination_func = lambda v=viewer: threading.Thread(
        target=v.scan_pagination_pages,daemon=True).start()
    viewer.go_to_page_func = lambda target_page, v=viewer: threading.Thread(
        target=v.go_to_page, args=(target_page,), daemon=True).start()
    viewer.go_to_page_func = lambda target_page, v=viewer: threading.Thread(
        target=v.go_to_page, args=(target_page,), daemon=True).start()

    viewer.show()
    try: sys.exit(app.exec_())
    finally:
        for p in scrcpy_ps: p.terminate(); p.wait()
        if log_fp[0]: log_fp[0].close(); print("📄 Log saved:")

if __name__=="__main__":
    main()


