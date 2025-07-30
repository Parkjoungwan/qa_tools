#!/usr/bin/env bash

# adb_logcat_targeted.sh
# 지정된 기기 serial에만 logcat 필터 적용 (하드코딩된 값 사용)

set -euo pipefail

# 타겟 기기 serial (하드코딩)
TARGET_SERIAL="52006ed48cddb50f"

# 연결된 기기 목록 확인
DEVICES=($(adb devices | awk 'NR>1 && $2=="device" {print $1}'))

# 타겟 기기가 연결되어 있는지 확인
FOUND=false
for serial in "${DEVICES[@]}"; do
  if [ "$serial" = "$TARGET_SERIAL" ]; then
    FOUND=true
    break
  fi
done

if [ "$FOUND" = true ]; then
  echo "✅ 타겟 기기 ($TARGET_SERIAL) 에 로그캣 필터 적용 중..."
  # Unity는 Info 이상, Crash/Fatal은 Error, 나머지는 Warning 이상
  adb -s "$TARGET_SERIAL" logcat Unity:I Crash:E Fatal:E '*:W'
else
  echo "❌ 타겟 기기 ($TARGET_SERIAL)를 찾을 수 없습니다."
  echo "🔎 연결된 기기 목록:"
  for s in "${DEVICES[@]}"; do
    echo " - $s"
  done
  exit 1
fi

