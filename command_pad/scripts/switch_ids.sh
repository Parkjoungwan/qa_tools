#!/bin/bash

ENV_FILE="../.env"

# 현재 활성화된 학년의 ID/PW 추출
ACTIVE_ID1=$(grep -v '^#' "$ENV_FILE" | grep '^ID_1=' | cut -d '=' -f2)
ACTIVE_PW1=$(grep -v '^#' "$ENV_FILE" | grep '^PW_1=' | cut -d '=' -f2)
ACTIVE_ID2=$(grep -v '^#' "$ENV_FILE" | grep '^ID_2=' | cut -d '=' -f2)
ACTIVE_PW2=$(grep -v '^#' "$ENV_FILE" | grep '^PW_2=' | cut -d '=' -f2)

# 백업
cp "$ENV_FILE" "$ENV_FILE.bak"

# 스왑 적용
sed -i '' "s/^ID_1=.*/ID_1=$ACTIVE_ID2/" "$ENV_FILE"
sed -i '' "s/^PW_1=.*/PW_1=$ACTIVE_PW2/" "$ENV_FILE"
sed -i '' "s/^ID_2=.*/ID_2=$ACTIVE_ID1/" "$ENV_FILE"
sed -i '' "s/^PW_2=.*/PW_2=$ACTIVE_PW1/" "$ENV_FILE"

echo "🔄 현재 활성화된 학년의 ID/PW가 스위치 되었습니다."

