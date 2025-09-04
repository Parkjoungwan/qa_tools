#!/usr/bin/env bash
source "$(dirname "$0")/.env"

set -euo pipefail

# 기본 대상
DEFAULT_DEVICES=($DEVICE1 "$DEVICE2")

DEVICES=($"$@")
[[ ${#DEVICES[@]} -eq 0 ]] && DEVICES=("${DEFAULT_DEVICES[@]}")

for SERIAL in "${DEVICES[@]}"; do
  echo "📴  Closing apps on $SERIAL …"

  # 1) 홈으로 이동 – 전면 Activity ↓
  adb -s "$SERIAL" shell input keyevent 3

  # 2) 백그라운드 프로세스 전체 kill
  adb -s "$SERIAL" shell am kill-all

  # 3) 사용자 설치 앱 force-stop (시스템 앱 제외)
  adb -s "$SERIAL" shell \
      "pm list packages -3 | cut -d':' -f2 | xargs -n1 am force-stop" \
      || true

  # 4) 화면 잠금
  echo "🔒  Locking $SERIAL …"
  adb -s "$SERIAL" shell input keyevent 224
  adb -s "$SERIAL" shell input keyevent 26
  adb -s "$SERIAL" shell locksettings lock || true
done

echo "✅  Done."

