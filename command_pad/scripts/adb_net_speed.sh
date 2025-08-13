#!/usr/bin/env bash
set -euo pipefail

# --- 설정 ---
DEVICE_ID="52006ed48cddb50f"
APP_PACKAGE="com.kyowon.aicando.elem"
APP_ACTIVITY="com.unity3d.player.UnityPlayerActivity"

INTERVAL="${INTERVAL:-1}"   # 초
SAMPLES="${SAMPLES:-0}"     # 0이면 무한

# --- 유틸 ---
adb_s() { adb -s "$DEVICE_ID" "$@"; }

# 0) 디바이스 연결 확인
if ! adb_s get-state >/dev/null 2>&1; then
  echo "ERROR: 디바이스($DEVICE_ID)이 연결/신뢰되지 않았습니다. 'adb devices' 확인."
  exit 1
fi

# 1) 앱 포그라운드 확인 후 없으면 실행
FOCUSED_LINE=$(adb_s shell "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' || true")
if ! echo "$FOCUSED_LINE" | grep -q "$APP_PACKAGE"; then
  echo "App not in foreground on $DEVICE_ID. Starting..."
  adb_s shell am start -n "$APP_PACKAGE/$APP_ACTIVITY" >/dev/null
  # 포그라운드 진입 대기(최대 10초)
  for i in $(seq 1 20); do
    sleep 0.5
    FOCUSED_LINE=$(adb_s shell "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp' || true")
    if echo "$FOCUSED_LINE" | grep -q "$APP_PACKAGE"; then
      echo "App is now in foreground."
      break
    fi
    [[ $i -eq 20 ]] && { echo "WARN: 포그라운드 확인 실패(계속 진행)"; }
  done
else
  echo "App already in foreground on $DEVICE_ID."
fi

# 2) 앱 UID 조회
UID_LINE=$(adb_s shell "dumpsys package $APP_PACKAGE | grep -m1 'userId=' || true")
if [[ -z "$UID_LINE" ]]; then
  echo "ERROR: 패키지 정보를 찾을 수 없습니다: $APP_PACKAGE"
  exit 2
fi
APP_UID=$(echo "$UID_LINE" | sed -E 's/.*userId=([0-9]+).*/\1/')
echo "# Device: $DEVICE_ID  Package: $APP_PACKAGE  UID: $APP_UID  interval=${INTERVAL}s"
echo "# Time, BytesDelta, Rate(B/s), Rate(MB/s), Rate(Mb/s)"

# 3) UID 누계 바이트 합산 함수 (dumpsys netstats detail)

get_uid_total_bytes() {
  # 최신 카운터 반영을 위해 --poll 사용
  adb_s shell dumpsys netstats --poll detail | \
  awk -v uid="$APP_UID" '
    function add_bucket_line() {
      for (i=1;i<=NF;i++) {
        if ($i ~ /^rxBytes=/) { split($i,a,"="); rx+=a[2] }
        else if ($i ~ /^txBytes=/) { split($i,a,"="); tx+=a[2] }
      }
    }
    /UID stats:/ { in_uid_section=1; pending_done=0; next }

    # 대상 UID 구간 시작(라인 배치에 상관없이 uid=숫자 포함 + tag=0x0 기준)
    in_uid_section && $0 ~ ("uid=" uid) && $0 ~ /tag=0x0/ { capture=1; next }

    # Pending bytes 합산 (한 번만)
    in_uid_section && !pending_done && $0 ~ /Pending bytes:/ {
      # 형식: "Pending bytes: 744" 또는 내부적으로 rx/tx 반영된 총합
      # 편의상 pending을 전체 바이트로 더해주되, 일부 빌드에선 값이 없을 수 있음
      for (i=1;i<=NF;i++) if ($i ~ /^[0-9]+$/) { pending+=$i }
      pending_done=1; next
    }

    # 버킷 합산 (capture 중에만)
    capture && /bucketStart=/ { add_bucket_line(); next }

    # 다음 ident 블록이 오면 현 uid/tag 집계 종료(기기별 포맷 차이 흡수)
    capture && /^ *ident=\[\[/ { capture=0; next }

    END { print (rx+tx+pending)+0 }
  '
}


# 4) 샘플링 루프
prev_total=$(get_uid_total_bytes)
if ! [[ "$prev_total" =~ ^[0-9]+$ ]]; then
  echo "ERROR: 누적 바이트 파싱 실패."
  exit 3
fi

count=0
while :; do
  sleep "$INTERVAL"
  now=$(date +"%Y-%m-%d %H:%M:%S")
  curr_total=$(get_uid_total_bytes)
  if ! [[ "$curr_total" =~ ^[0-9]+$ ]]; then
    echo "WARN: 파싱 실패(샘플 건너뜀)"; continue
  fi
  delta=$(( curr_total - prev_total ))
  prev_total=$curr_total

  rate_bps=$(awk -v d="$delta" -v s="$INTERVAL" 'BEGIN{printf "%.2f", d/s}')
  rate_MBps=$(awk -v r="$rate_bps" 'BEGIN{printf "%.3f", r/1048576}')
  rate_Mbps=$(awk -v r="$rate_bps" 'BEGIN{printf "%.3f", (r*8)/1000000}')

  printf "%s, %d, %s, %s, %s\n" "$now" "$delta" "$rate_bps" "$rate_MBps" "$rate_Mbps"

  if [[ "$SAMPLES" -gt 0 ]]; then
    count=$((count+1))
    [[ "$count" -ge "$SAMPLES" ]] && break
  fi
done

