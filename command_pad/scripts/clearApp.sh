#!/usr/bin/env bash
# close_and_lock.sh
#
#   모든 실행 앱 종료 → 화면 잠금
#
# 사용법
#   ./close_and_lock.sh                 # 기본 두 기기만
#   ./close_and_lock.sh <serial…>       # 원하는 serial 지정
#
# ──────────────────────────────────────────────────────────────
set -euo pipefail

# 기본 대상
DEFAULT_DEVICES=("520068a9435db5d5" "52006ed48cddb50f")

DEVICES=("$@")
[[ ${#DEVICES[@]} -eq 0 ]] && DEVICES=("${DEFAULT_DEVICES[@]}")

for SERIAL in "${DEVICES[@]}"; do
  echo "📴  Closing apps on $SERIAL …"

  # 1) 홈으로 이동 – 전면 Activity ↓
  adb -s "$SERIAL" shell input keyevent 3      # KEYCODE_HOME :contentReference[oaicite:0]{index=0}

  # 2) 백그라운드 프로세스 전체 kill
  adb -s "$SERIAL" shell am kill-all           # kill-all :contentReference[oaicite:1]{index=1}

  # 3) 사용자 설치 앱 force-stop (시스템 앱 제외)
  adb -s "$SERIAL" shell \
      "pm list packages -3 | cut -d':' -f2 | xargs -n1 am force-stop" \
      || true                                  # -3 옵션 :contentReference[oaicite:2]{index=2}

  # 4) 화면 잠금
  echo "🔒  Locking $SERIAL …"
  adb -s "$SERIAL" shell input keyevent 224    # KEYCODE_WAKEUP :contentReference[oaicite:3]{index=3}
  adb -s "$SERIAL" shell input keyevent 26     # KEYCODE_POWER  :contentReference[oaicite:4]{index=4}
  adb -s "$SERIAL" shell locksettings lock || true
done

echo "✅  Done."

