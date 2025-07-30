"""
멀티 기기 로그인 / 로그아웃 실행기
─────────────────────────────────────────────
각 서브 프로세스:
  ADB_SERIAL=<serial>
  ANDROID_SERIAL=<serial>
  LOGIN_INDEX=<1,2,3…>
"""

import subprocess, os, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_MOD = "tests.login_logout"

def list_devices() -> list[str]:
    out = subprocess.check_output("adb devices", shell=True, text=True)
    return [ln.split()[0] for ln in out.splitlines()[1:] if "\tdevice" in ln]

def run_on_device(serial: str, idx: int, login_only: bool):
    env = os.environ.copy()
    env["ADB_SERIAL"] = serial
    env["ANDROID_SERIAL"] = serial
    env["LOGIN_INDEX"] = str(idx)
    arg = "0" if login_only else "1"
    cmd = ["python", "-m", SCRIPT_MOD, arg]
    proc = subprocess.Popen(cmd, env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    out, _ = proc.communicate()
    return serial, proc.returncode, out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--login",  action="store_true", help="로그인만")
    g.add_argument("--logout", action="store_true", help="로그인+로그아웃(기본)")
    args = ap.parse_args()
    login_only = args.login

    devs = list_devices()
    if not devs:
        print("❌  기기가 없습니다."); exit(1)
    print(f"🔎  감지된 기기: {devs}")

    with ThreadPoolExecutor(max_workers=len(devs)) as ex:
        futs = [ex.submit(run_on_device, s, i+1, login_only)
                for i, s in enumerate(devs)]
        for f in as_completed(futs):
            serial, rc, output = f.result()
            print(f"\n===== [{serial}] RC={rc} =====")
            print(output)

