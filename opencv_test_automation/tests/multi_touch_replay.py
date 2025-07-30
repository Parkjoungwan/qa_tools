# tests/multi_touch_replay.py
"""
멀티-디바이스(또는 단일) 터치·스와이프·캡처 리플레이 (log v3 + repeat)
────────────────────────────────────────────────────────
로그 형식 (공백·탭 구분, 헤더 무시)

type  elapsed(s)  serial              x1    y1    x2    y2  duration(ms)
tap   30.64       52006ed48cddb50f   805   165
swipe 51.68       52006ed48cddb50f  1387  1017  1375   335   584
cap   63.50       52006ed48cddb50f
…

• tap   : x1 y1 값 사용 → adb … input tap  
• swipe : x1 y1 x2 y2 duration 사용 → adb … input swipe  
• cap   : 스크린샷을 log_images/<stem>_<DATE>/ 에 저장  
• --repeat N  옵션으로 로그 전체를 N 회 반복 실행
"""

import sys, time, subprocess, multiprocessing as mp, datetime, argparse
from pathlib import Path

# ───── 1. 로그 파싱 ───────────────────────────────────
def load_events(path: Path):
    events: dict[str, list[tuple]] = {}
    with path.open() as f:
        for ln in f:
            if ln.strip().startswith(("tap", "swipe", "cap")):
                parts = ln.split()
                kind, t, serial = parts[0], float(parts[1]), parts[2]
                if kind == "tap":
                    x, y = map(int, parts[3:5]); args = (x, y)
                elif kind == "swipe":
                    x1, y1, x2, y2, dur = map(int, parts[3:8])
                    args = (x1, y1, x2, y2, dur)
                else:          # cap
                    args = ()
                events.setdefault(serial, []).append((t, kind, args))
    if not events:
        raise ValueError("로그에서 유효한 이벤트를 찾지 못했습니다.")
    for ev in events.values():
        ev.sort(key=lambda e: e[0])
    return events

# ───── 2. ADB 헬퍼 ────────────────────────────────────
def adb(serial, *cmd, capture=False):
    full = ["adb", "-s", serial, *map(str, cmd)]
    if capture:
        return subprocess.check_output(full)
    subprocess.check_call(full,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)

def save_screencap(serial: str, dest: Path):
    img = adb(serial, "exec-out", "screencap", "-p", capture=True)
    dest.write_bytes(img)

# ───── 3. 워커 프로세스 ───────────────────────────────
def worker(serial, evs, start_epoch, out_dir: Path,
           repeat: int, cycle_gap: float):
    total_dur = evs[-1][0]            # 마지막 이벤트 elapsed
    cycle_offset = total_dur + cycle_gap
    for cycle in range(repeat):
        base = start_epoch + cycle * cycle_offset
        for t, kind, args in evs:
            time.sleep(max(0, base + t - time.time()))
            if kind == "tap":
                x, y = args
                adb(serial, "shell", "input", "tap", x, y)
            elif kind == "swipe":
                x1, y1, x2, y2, dur = args
                adb(serial, "shell", "input", "swipe", x1, y1, x2, y2, dur)
            else:  # cap
                fname = f"{serial}_cycle{cycle+1}_{t:.2f}.png"
                save_screencap(serial, out_dir / fname)
            print(f"[{serial}] {kind}   cycle {cycle+1}/{repeat}  @ {t:.2f}s")

# ───── 4. 메인 ────────────────────────────────────────
def main(logfile: str, repeat: int, gap: float):
    path = Path(logfile)
    if not path.exists():
        print(f"❌  파일 없음: {path}"); sys.exit(1)

    events = load_events(path)
    out_dir = (Path("log_images") /
               f"{path.stem}_{datetime.datetime.now():%Y%m%d_%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"📑  기기 {len(events)}대, 이벤트 {sum(len(v) for v in events.values())}개")
    print(f"🔁  반복 횟수 : {repeat} (cycle gap {gap}s)")
    print(f"🖼️   스크린샷 저장 : {out_dir}")

    start_epoch = time.time() + 3
    print("⏳  3초 뒤 리플레이 시작…"); time.sleep(3)

    procs = []
    for serial, evs in events.items():
        p = mp.Process(target=worker,
                       args=(serial, evs, start_epoch, out_dir, repeat, gap))
        p.start(); procs.append(p)

    for p in procs: p.join()
    print("✅  전체 리플레이 완료")

# ───── 5. CLI ────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("log", help="터치/스와이프/캡처 로그 파일")
    ap.add_argument("--repeat", "-n", type=int, default=1,
                    help="로그 반복 실행 횟수(기본 1)")
    ap.add_argument("--gap", type=float, default=1.0,
                    help="사이클 사이 간격(sec, 기본 1.0)")
    args = ap.parse_args()

    try:
        main(args.log, args.repeat, args.gap)
    except Exception as e:
        print(f"❌  오류: {e}")
        sys.exit(1)

