#!/usr/bin/env python3
"""
run.py
────────────────────────────────────────────────────────
루트에서 여러 테스트 스크립트(tests.패키지의 모듈)를
사용자 지정 순서와 반복 횟수로 실행한다.

사용 예
──────
# 1) ai_math 한 번 실행
$ python run.py ai_math

# 2) ai_math 3회, login_logout 1회
$ python run.py ai_math*3 login_logout

# 3) ai_math 5회, ai_report 2회, 각 모듈에 추가 인자 전달
$ python run.py ai_math*5 ai_report*2 -- --loops 5 --fast

인자 규칙
────────
▪ positional args : <module_name>[*N]
    - tests.<module_name>  가 import 가능해야 함
    - *N  을 붙이면 해당 모듈을 N회 반복 (생략 시 1)
▪  --  이후의 모든 인자는 **각 서브 모듈**에 그대로 전달
"""

import argparse
import importlib
import os
import subprocess
import sys
import shlex
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
TESTS_PACKAGE = "tests"


# ─────────────────────────────────────────────────────────
def parse_targets(args: list[str]) -> list[tuple[str, int]]:
    """['ai_math*3','login_logout'] → [('ai_math',3),('login_logout',1)]"""
    targets = []
    for arg in args:
        if "*" in arg:
            mod, cnt = arg.split("*", 1)
            if not cnt.isdigit() or int(cnt) <= 0:
                sys.exit(f"❌  잘못된 반복 횟수: {arg}")
            targets.append((mod, int(cnt)))
        else:
            targets.append((arg, 1))
    return targets


def check_module_exists(mod_name: str):
    """tests.mod_name 에 해당하는 파일이 존재하는지 확인."""
    module_path = ROOT / "opencv_test_automation" / TESTS_PACKAGE.replace('.', '/') / f"{mod_name}.py"
    if not module_path.exists():
        sys.exit(f"❌  모듈 파일 {module_path} 이(가) 없습니다.")


def run_module(mod_name: str, extra: list[str]):
    module_path = ROOT / "opencv_test_automation" / TESTS_PACKAGE.replace('.', '/') / f"{mod_name}.py"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    cmd = ["python", str(module_path), *extra]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env
    )
    out, _ = proc.communicate()
    return proc.returncode, out


# ─────────────────────────────────────────────────────────
def main():
    # split argv into <targets> ... -- <extra>
    if "--" in sys.argv:
        idx = sys.argv.index("--")
        raw_targets = sys.argv[1:idx]
        extra_args = sys.argv[idx + 1 :]
    else:
        raw_targets = sys.argv[1:]
        extra_args = []

    if not raw_targets:
        print(__doc__)
        sys.exit(0)

    targets = parse_targets(raw_targets)

    # 모듈 존재 확인
    for mod, _cnt in targets:
        check_module_exists(mod)

    print("📝 실행 계획:", ", ".join([f"{m}×{c}" for m, c in targets]))
    if extra_args:
        print("➕ 추가 인자:", extra_args)

    seq_no = 1
    for mod, cnt in targets:
        for i in range(cnt):
            tag = f"{mod} [{i+1}/{cnt}]"
            print(f"\n┏━━━━━━━━━━━━━━  {tag}  ━━━━━━━━━━━━━━┓")
            rc, out = run_module(mod, extra_args)
            print(out.rstrip())
            print(f"┗━━ 종료 코드 {rc} ━━━━━━━━━━━━━━━━━━━━━━━┛")
            if rc != 0:
                print("⚠️  오류가 발생하여 이후 실행을 중단합니다.")
                sys.exit(rc)
            seq_no += 1

    print("\n✅  모든 테스트 완료!")


if __name__ == "__main__":
    main()

