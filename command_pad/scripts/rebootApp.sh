#!/bin/bash

TARGET_SERIAL="52006ed48cddb50f"
ADB="adb -s $TARGET_SERIAL"

# 디바이스 연결 확인
if ! adb devices | grep -q "^$TARGET_SERIAL[[:space:]]device$"; then
  echo "❌ 대상 디바이스($TARGET_SERIAL)가 연결되어 있지 않습니다."
  exit 1
fi

# 현재 포그라운드 앱 패키지명 추출 (macOS 호환)
PKG="com.kyowon.aicando.elem"

echo "🎯 타겟 앱 패키지명: $PKG"

# 앱 강제 종료
$ADB shell am force-stop "$PKG"
echo "🛑 앱 종료됨"

# 실행 가능한 액티비티 검색
ACTIVITY=$($ADB shell dumpsys package "$PKG" | grep -A 20 "android.intent.action.MAIN" \
  | grep "$PKG" | grep -o "[a-zA-Z0-9_.]*\/[a-zA-Z0-9_.]*" | head -1)

if [ -z "$ACTIVITY" ]; then
  echo "❌ 실행 가능한 MAIN 액티비티를 찾을 수 없습니다."
  exit 1
fi

echo "🚀 앱 재실행: $ACTIVITY"
$ADB shell am start -n "$ACTIVITY"
echo "✅ 앱 재실행됨"

