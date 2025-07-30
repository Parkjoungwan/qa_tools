#!/usr/bin/env bash
# adb_capture_pull_clean.sh
#
# 목록 첫 번째 기기에서만 캡처 → PC로 pull → 원격 파일 삭제
# 사용법:
#   ./adb_capture_pull_clean.sh [OPTIONAL_SAVE_DIR]
#   (SAVE_DIR 없으면 현재 디렉터리에 저장)

set -euo pipefail

# ──────────────────────────────────────────────
# 1) 첫 번째 device 직렬번호 가져오기
SERIAL="$(adb devices | awk 'NR==3 && /device$/{print $1}')"
if [[ -z "$SERIAL" ]]; then
  echo "❌  연결된 기기가 없습니다." >&2
  exit 1
fi
ADB="adb -s $SERIAL"
echo "📱  대상 기기: $SERIAL"
# ──────────────────────────────────────────────

# 2) 저장 경로
SAVE_DIR="${1:-.}"
mkdir -p "$SAVE_DIR"

# 3) 파일명 (타임스탬프)
TS="$(date +%Y%m%d_%H%M%S)"
REMOTE_PATH="/sdcard/screen_${TS}.png"
LOCAL_PATH="${SAVE_DIR}/screen_${TS}.png"

# 4) 캡처 → pull → 원격 삭제
echo "📸  Capturing screen …"
$ADB shell screencap -p "$REMOTE_PATH"

echo "⬇️  Pulling to PC → $LOCAL_PATH"
$ADB pull "$REMOTE_PATH" "$LOCAL_PATH"

echo "🧹  Removing remote file"
$ADB shell rm "$REMOTE_PATH"

echo "✅  Done! Saved at: $LOCAL_PATH"

