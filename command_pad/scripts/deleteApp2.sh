#!/usr/bin/env bash
# uninstall_app.sh

TARGET_SERIAL="R9TR90M8P4Y"
ADB="adb -s $TARGET_SERIAL"

# ── 연결 확인 ──────────────────────────────
if ! adb devices | grep -q "^$TARGET_SERIAL[[:space:]]device$"; then
  echo "❌ 대상 디바이스($TARGET_SERIAL)가 연결되어 있지 않습니다."
  exit 1
fi

# ── 타겟 앱 패키지명 ───────────────────────
PKG="com.kyowon.aicando.elem"
echo "🎯 삭제할 패키지: $PKG"

# ── 앱 삭제 ───────────────────────────────
if $ADB uninstall "$PKG" >/dev/null 2>&1; then
  echo "🗑 앱 삭제 완료"
else
  echo "❌ 앱 삭제 실패"
  exit 1
fi

