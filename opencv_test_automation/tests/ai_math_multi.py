"""
tests/ai_math_multi.py
────────────────────────────────────────────────────────
두 대 이상 Android 기기에서 **AI Math 시나리오**(tests.ai_math)를
동시에 실행하기 위한 런처 스크립트입니다.

각 서브-프로세스에는
  • ADB_SERIAL=<serial>   (utils.adb_utils 가 인식)
  • ANDROID_SERIAL=<serial> (adb 표준)
를 주입하여, 기기별로 독립 실행됩니다.

사용 예
  python -m tests.ai_math_multi
  python -m tests.ai_math_multi --loops 5   # (옵션) 루프 횟수 전달
"""

import subprocess, os, argparse, shlex
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_MOD = "tests.ai_math"      # 실행할 모듈


# ─────────────────────────────────────────────────────────
def list_devices() -> list[str]:
    """'adb devices' 목록에서 연결 상태가 'device' 인 직렬번호만 추출."""
    out = subprocess.check_output("adb devices", shell=True, text=True)
    return [ln.split()[0] for ln in out.splitlines()[1:] if "\tdevice" in ln]


# ─────────────────────────────────────────────────────────
def run_on_device(serial: str, extra_args: str | None):
    """
    한 기기(serial)에서 tests.ai_math 모듈을 서브-프로세스로 실행.
    extra_args 는 사용자가 넘긴 모듈용 인자를 그대로 전달한다.
    """
    env = os.environ.copy()
    env["ADB_SERIAL"] = serial
    env["ANDROID_SERIAL"] = serial

    cmd = ["python", "-m", SCRIPT_MOD]
    if extra_args:
        cmd += shlex.split(extra_args)

    proc = subprocess.Popen(cmd,
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True)
    output, _ = proc.communicate()
    return serial, proc.returncode, output


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Run AI-Math automation on all connected devices."
    )
    ap.add_argument("--args", metavar='"ARG STRING"',
                    help="추가로 tests.ai_math 에 넘길 인자 문자열 "
                         "(예: --loops 5 --fast)")
    args = ap.parse_args()

    devices = list_devices()
    if not devices:
        print("❌  연결된 기기가 없습니다."); exit(1)

    print(f"🔎  감지된 기기: {devices}")

    with ThreadPoolExecutor(max_workers=len(devices)) as ex:
        futs = [ex.submit(run_on_device, s, args.args)
                for s in devices]
        for fut in as_completed(futs):
            serial, rc, out = fut.result()
            print(f"\n===== [{serial}] 종료 코드 {rc} =====")
            print(out)

