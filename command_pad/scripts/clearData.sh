#!/usr/bin/env bash
# cleardata_force_stop_restart.sh

TARGET_SERIAL="52006ed48cddb50f"
ADB="adb -s $TARGET_SERIAL"

# ── 연결 확인 ──────────────────────────────
if ! adb devices | grep -q "^$TARGET_SERIAL[[:space:]]device$"; then
  echo "❌ 대상 디바이스($TARGET_SERIAL)가 연결되어 있지 않습니다."
  exit 1
fi

# ── 타겟 앱 패키지명 (하드코딩) ───────────────
PKG="com.kyowon.aicando.elem"
echo "🎯 타겟 패키지: $PKG"

# ── 데이터 초기화 + 강제 종료 ───────────────
$ADB shell pm clear "$PKG"   >/dev/null
$ADB shell am force-stop "$PKG"
echo "🧹 데이터 초기화 & 종료 완료"
sleep 3                          # ← 충분한 딜레이

# ── 실행 가능한 MAIN/LAUNCHER 탐색 ────────
ACTIVITY=$(
  $ADB shell dumpsys package "$PKG" |
    grep -A 20 "android.intent.action.MAIN" |
    grep "$PKG" |
    grep -o "[A-Za-z0-9_.]*/[A-Za-z0-9_.]*" |
    head -1
)

if [[ -z "$ACTIVITY" ]]; then
  echo "❌ MAIN 액티비티를 찾을 수 없습니다."
  exit 1
fi

echo "🚀 앱 재실행: $ACTIVITY"

# ── 시도 1: am start ───────────────────────
if $ADB shell am start -n "$ACTIVITY" >/dev/null 2>&1; then
  echo "✅ 성공 (am start)"
  exit 0
fi

# ── 시도 2: monkey fallback ────────────────
if $ADB shell monkey --pct-syskeys 0 -p "$PKG" -c android.intent.category.LAUNCHER 1 \
     >/dev/null 2>&1; then
  echo "✅ 성공 (monkey fallback)"
  exit 0
fi

echo "❌ 재실행 실패"
exit 1

