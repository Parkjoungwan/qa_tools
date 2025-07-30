# tests/long_text_input_multi.py
"""
멀티-디바이스 “긴 텍스트 입력” 런처
────────────────────────────────────────────────────────────
연결된 모든 Android 기기에서 `tests.long_text_input` 시나리오를
동시에 실행한다.

각 서브-프로세스에는
  • ADB_SERIAL=<serial>
  • ANDROID_SERIAL=<serial>
가 주입되어, 디바이스 충돌 없이 독립 실행된다.

사용 예
──────
python -m tests.long_text_input_multi
"""

import subprocess, os
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_MOD = "tests.long_text_input"


# ─────────────────────────────────────────────────────────
def list_devices() -> list[str]:
    """adb devices 출력에서 'device' 상태 시리얼만 추출."""
    out = subprocess.check_output("adb devices", shell=True, text=True)
    return [ln.split()[0] for ln in out.splitlines()[1:] if "\tdevice" in ln]


def run_on_device(serial: str):
    """특정 디바이스에서 long_text_input 서브-모듈 실행."""
    env = os.environ.copy()
    env["ADB_SERIAL"] = serial
    env["ANDROID_SERIAL"] = serial

    cmd = ["python", "-m", SCRIPT_MOD]
    proc = subprocess.Popen(cmd,
                            env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True)
    output, _ = proc.communicate()
    return serial, proc.returncode, output


# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    devices = list_devices()
    if not devices:
        print("❌  연결된 기기가 없습니다.")
        exit(1)

    print(f"🔎  감지된 기기: {devices}")

    with ThreadPoolExecutor(max_workers=len(devices)) as ex:
        futures = [ex.submit(run_on_device, d) for d in devices]
        for fut in as_completed(futures):
            serial, rc, out = fut.result()
            print(f"\n===== [{serial}] 종료 코드 {rc} =====")
            print(out.rstrip())

