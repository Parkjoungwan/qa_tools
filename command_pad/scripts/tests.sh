#!/bin/bash

TARGET_SERIAL="520068a9435db5d5"
PACKAGE_NAME="com.kyowon.aicando.elem"

ADB="adb -s $TARGET_SERIAL"

# 디바이스 연결 확인
if ! adb devices | grep -q "^$TARGET_SERIAL[[:space:]]device$"; then
  echo "❌ 디바이스가 연결되지 않았습니다: $TARGET_SERIAL"
  exit 1
fi

echo "🎯 대상 디바이스 연결 확인됨: $TARGET_SERIAL"

# 실행 가능한 MAIN 액티비티 추출
ACTIVITY=$($ADB shell dumpsys package "$PACKAGE_NAME" | grep -A 20 "android.intent.action.MAIN" \
  | grep "$PACKAGE_NAME" | grep -o "[a-zA-Z0-9_.]*\/[a-zA-Z0-9_.]*" | head -1)

if [ -z "$ACTIVITY" ]; then
  echo "❌ 실행 가능한 MAIN 액티비티를 찾을 수 없습니다."
  echo "📎 참고: 매니페스트 내 exported=\"true\" 여부나 보호자 앱 경유 여부를 확인해보세요."
  exit 1
fi

echo "🚀 실행할 액티비티: $ACTIVITY"

# 앱 실행
$ADB shell am start -n "$ACTIVITY"
`
