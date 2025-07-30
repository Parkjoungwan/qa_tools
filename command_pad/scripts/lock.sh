#!/usr/bin/env bash
# lock_screens.sh
#
# 요구 사항:
#   - ADB가 PATH에 잡혀 있어야 합니다.
#   - Android 8.0+ 기기는 locksettings lock 명령을 지원합니다.
#
# 사용법:
#   ./lock_screens.sh                 # 기본 두 디바이스만 잠금
#   ./lock_screens.sh <serial…>       # 원하는 serial 목록을 잠금
#
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# ★ 기본 대상 기기 목록
DEFAULT_DEVICES=("520068a9435db5d5" "52006ed48cddb50f")

# 인자가 있으면 인자를, 없으면 기본 목록을 사용
DEVICES=("$@")
[[ ${#DEVICES[@]} -eq 0 ]] && DEVICES=("${DEFAULT_DEVICES[@]}")

for SERIAL in "${DEVICES[@]}"; do
  echo "🔒  Locking screen on $SERIAL …"

  # 1) 잠자고 있을 수도 있으니 먼저 깨움 (무해: 이미 화면이 켜져 있으면 영향 없음)
  adb -s "$SERIAL" shell input keyevent 224    # KEYCODE_WAKEUP

  # 2) 전원 버튼 토글 → 화면 Off & 잠금
  adb -s "$SERIAL" shell input keyevent 26     # KEYCODE_POWER

  # 3) Android 8.0+에서 지원: 잠금 상태를 명시적으로 강제
  adb -s "$SERIAL" shell locksettings lock || true
done

echo "✅  All requested devices locked."

