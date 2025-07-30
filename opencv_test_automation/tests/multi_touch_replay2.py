#!/usr/bin/env python3
# tests/multi_touch_replay.py
"""
멀티-디바이스 터치·스와이프·캡처 리플레이 (multi-file + per-cycle repeat)
─────────────────────────────────────────────────────────────────────────
예시
python -m tests.multi_touch_replay \
       logA.log logB.log \
       --repeat 3 \
       --log-gap 2.0 \
       --cycle-gap 5.0

실행 순서 : [logA → logB] × 3회
· 각 로그 사이에는 2 초 대기
· 1회 사이클(= logA+logB) 이 끝나면 5 초 대기 후 다음 사이클
"""

import sys, time, subprocess, multiprocessing as mp, datetime, argparse
from pathlib import Path
from typing import List, Dict, Tuple


# ───── 1. 로그 파싱 ───────────────────────────────────
def load_events(path: Path) -> Dict[str, List[Tuple]]:
    """로그 1개를 읽어 {serial: [(elapsed, kind, args)…]} 반환"""
    events: Dict[str, List[Tuple]] = {}
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
                else:  # cap
                    args = ()
                events.setdefault(serial, []).append((t, kind, args))
    if not events:
        raise ValueError(f"{path}: 유효한 이벤트를 찾지 못했습니다.")
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
def worker(serial: str, evs: List[Tuple], start_epoch: float,
           out_dir: Path):
    for t, kind, args in evs:
        time.sleep(max(0, start_epoch + t - time.time()))
        if kind == "tap":
            x, y = args
            adb(serial, "shell", "input", "tap", x, y)
        elif kind == "swipe":
            x1, y1, x2, y2, dur = args
            adb(serial, "shell", "input", "swipe",
                x1, y1, x2, y2, dur)
        else:  # cap
            fname = f"{serial}_{t:.2f}.png"
            save_screencap(serial, out_dir / fname)
        print(f"[{serial}] {kind} @ {t:.2f}s")


# ───── 4. 로그 하나 재생 ──────────────────────────────
def replay_single(path: Path, log_gap: float):
    print(f"\n=== ▶ {path.name} 재생 시작 ===")
    events = load_events(path)
    out_dir = (Path("log_images") /
               f"{path.stem}_{datetime.datetime.now():%Y%m%d_%H%M%S}")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"📑  기기 {len(events)}대, "
          f"이벤트 {sum(len(v) for v in events.values())}개")
    print(f"🖼️   스크린샷 저장: {out_dir}")

    start_epoch = time.time() + 3
    print("⏳  3초 뒤 재생…"); time.sleep(3)

    procs = []
    for serial, evs in events.items():
        p = mp.Process(target=worker,
                       args=(serial, evs, start_epoch, out_dir))
        p.start(); procs.append(p)

    for p in procs: p.join()
    print(f"✅  {path.name} 재생 완료")

    time.sleep(log_gap)          # ── 로그 간 지연


# ───── 5. 메인 ────────────────────────────────────────
def main(log_paths: List[str], repeat: int,
         log_gap: float, cycle_gap: float):
    if repeat < 1:
        print("❌  --repeat 값은 1 이상이어야 합니다."); sys.exit(1)

    logs = [Path(p) for p in log_paths]
    for p in logs:
        if not p.exists():
            print(f"❌  파일 없음: {p}"); sys.exit(1)

    total_runs = len(logs) * repeat
    print(f"🔁  (logs={len(logs)}) × repeat({repeat}) = {total_runs}회 재생")
    print(f"   • 로그 간 지연   : {log_gap} s")
    print(f"   • 사이클 간 지연 : {cycle_gap} s")

    for cycle in range(repeat):
        if cycle > 0:
            print(f"\n— cycle gap {cycle_gap}s —"); time.sleep(cycle_gap)
        print(f"\n◆◆◆ Cycle {cycle+1}/{repeat} ◆◆◆")
        for path in logs:
            replay_single(path, log_gap)

    print("\n🎉  모든 로그 반복 재생 완료")


# ───── 6. CLI ────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+",
                    help="하나 이상 로그 파일 (지정 순서대로 재생)")
    ap.add_argument("--repeat", "-n", type=int, default=1,
                    help="로그 목록 자체를 반복할 횟수 (기본 1)")
    ap.add_argument("--log-gap", type=float, default=1.0,
                    help="각 로그 파일 사이 지연(sec, 기본 1.0)")
    ap.add_argument("--cycle-gap", type=float, default=1.0,
                    help="사이클(목록 1회) 간 지연(sec, 기본 1.0)")
    args = ap.parse_args()

    try:
        main(args.logs, args.repeat, args.log_gap, args.cycle_gap)
    except Exception as e:
        print(f"❌  오류: {e}")
        sys.exit(1)

