#!/bin/bash

TARGET_SERIAL="52006ed48cddb50f"

# 대상 디바이스가 연결되어 있는지 확인
if ! adb devices | grep -q "^$TARGET_SERIAL[[:space:]]device$"; then
  echo "❌ 대상 디바이스($TARGET_SERIAL)가 연결되어 있지 않습니다."
  exit 1
fi

ADB="adb -s $TARGET_SERIAL"

# 재부팅 명령
echo "🔄 기기 재시작 중..."
$ADB reboot

# 재부팅 명령은 비동기이므로, 이후 명령은 실행되지 않음
# 필요하다면, 재부팅 이후 adb 재접속을 기다리는 로직 추가 가능

