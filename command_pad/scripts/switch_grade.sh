#!/bin/bash

ENV_FILE="../.env"
TMP_FILE="../.env.tmp"
GRADES=("2학년" "4학년" "6학년")

cp "$ENV_FILE" "$ENV_FILE.bak"

# 현재 활성화된 학년 찾기
current=""
in_block=""
while IFS= read -r line; do
  if [[ "$line" =~ ^#([0-9]+학년)$ ]]; then
    in_block="${BASH_REMATCH[1]}"
    continue
  fi
  if [[ "$in_block" != "" && "$line" =~ ^ID_1= ]]; then
    current="$in_block"
    break
  fi
done < "$ENV_FILE"

if [ -z "$current" ]; then
  echo "❌ 활성화된 학년을 찾을 수 없습니다. .env 내용을 확인하세요."
  exit 1
fi

# 다음 학년 결정
next=""
for ((i = 0; i < ${#GRADES[@]}; i++)); do
  if [[ "${GRADES[i]}" == "$current" ]]; then
    next="${GRADES[(i + 1) % ${#GRADES[@]}]}"
    break
  fi
done

echo "🔁 $current → $next 로 전환 중..."

# 학년 블록만 주석 전환
in_block=""
> "$TMP_FILE"
while IFS= read -r line; do
  if [[ "$line" =~ ^#([0-9]+학년)$ ]]; then
    in_block="${BASH_REMATCH[1]}"
    echo "$line" >> "$TMP_FILE"
    continue
  fi

  if [[ "$in_block" == "$current" ]]; then
    if [[ "$line" =~ ^ID_ || "$line" =~ ^PW_ ]]; then
      echo "#$line" >> "$TMP_FILE"
    else
      echo "$line" >> "$TMP_FILE"
    fi
  elif [[ "$in_block" == "$next" ]]; then
    if [[ "$line" =~ ^#(ID_|PW_) ]]; then
      echo "${line#\#}" >> "$TMP_FILE"
    else
      echo "$line" >> "$TMP_FILE"
    fi
  else
    echo "$line" >> "$TMP_FILE"
  fi
done < "$ENV_FILE"

mv "$TMP_FILE" "$ENV_FILE"
echo "✅ 전환 완료 → $next"

