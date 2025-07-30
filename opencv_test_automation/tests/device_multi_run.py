# tests/device_multi_run.py
"""
범용 멀티-디바이스 테스트 런처
────────────────────────────────────────────────────────
• 첫 번째 위치 인수  : 실행할 모듈 이름 (tests.<name>)
• '--' 이후 인수들  : 그대로 서브 모듈에 전달
• 모든 연결 기기에 대해 병렬 실행
  환경변수:
      ADB_SERIAL=<serial>
      ANDROID_SERIAL=<serial>
      LOGIN_INDEX=<1,2,…>   (모듈이 사용하지 않으면 무시)
"""

import subprocess, os, sys, shlex
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

TESTS_PKG = "tests"         # 고정 패키지 경로


# ─────────────────── ADB 기기 목록 ─────────────────────
def list_devices() -> list[str]:
    out = subprocess.check_output("adb devices", shell=True, text=True)
    return [ln.split()[0] for ln in out.splitlines()[1:] if "\tdevice" in ln]


# ─────────────────── 실행 함수 ─────────────────────────
def run_on_device(serial: str, index: int, mod_name: str, extra_args: list[str]):
    env = os.environ.copy()
    env["ADB_SERIAL"]     = serial
    env["ANDROID_SERIAL"] = serial
    env["LOGIN_INDEX"]    = str(index)        # 필요 없는 모듈은 무시

    # PYTHONPATH 환경 변수 설정
    # 현재 device_multi_run.py가 있는 폴더의 상위 폴더 (opencv_test_automation)를 PYTHONPATH에 추가
    current_dir_for_pythonpath = Path(__file__).resolve().parent.parent.parent
    env["PYTHONPATH"] = str(current_dir_for_pythonpath) + os.pathsep + env.get("PYTHONPATH", "")

    module_path = current_dir_for_pythonpath / "opencv_test_automation" / TESTS_PKG / f"{mod_name}.py"
    cmd = [sys.executable, str(module_path), *extra_args]
    proc = subprocess.Popen(cmd, env=env,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True)
    output, _ = proc.communicate()
    return serial, proc.returncode, output


# ─────────────────── 메인 ──────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("사용법: python -m tests.device_multi_run <module> [-- extra args]")
        sys.exit(1)

    # 인자 분리: <module> ... -- <pass-thru>
    if "--" in sys.argv:
        sep = sys.argv.index("--")
        mod_name = sys.argv[1]
        extra_args = sys.argv[sep + 1 :]
    else:
        mod_name = sys.argv[1]
        extra_args = sys.argv[2:]

    devices = list_devices()
    if not devices:
        print("❌  연결된 기기가 없습니다.")
        sys.exit(1)

    print(f"🔎  감지된 기기: {devices}")
    print(f"▶️  실행 모듈: {TESTS_PKG}.{mod_name}  (추가 인자: {extra_args})")

    with ThreadPoolExecutor(max_workers=len(devices)) as ex:
        futs = [
            ex.submit(run_on_device, serial, idx + 1, mod_name, extra_args)
            for idx, serial in enumerate(devices)
        ]
        for fut in as_completed(futs):
            serial, rc, out = fut.result()
            print(f"\n===== [{serial}] 종료 코드 {rc} =====")
            print(out.rstrip())


if __name__ == "__main__":
    main()

