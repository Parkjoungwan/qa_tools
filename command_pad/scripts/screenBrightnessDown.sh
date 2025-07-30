#!/usr/bin/env bash
# set_brightness.sh
# 두 Android 기기의 화면 밝기를 80(0~255 범위)으로 설정

set -euo pipefail

# 기기 목록 (필요하면 추가·제거하세요)
DEVICES=(
  "52006ed48cddb50f"
  "520068a9435db5d5"
)

for SERIAL in "${DEVICES[@]}"; do
  echo "Setting brightness on device $SERIAL ..."
  adb -s "$SERIAL" shell settings put system screen_brightness 05
done

echo "Done."

