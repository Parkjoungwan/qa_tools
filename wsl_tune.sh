#!/usr/bin/env bash
# wsl_tune.sh - /etc/wsl.conf 생성/백업, 기본 설정 적용

set -euo pipefail

# 루트 권한 확인
if [[ $EUID -ne 0 ]]; then
  echo "이 스크립트는 루트로 실행해야 합니다. (sudo ./wsl_tune.sh)"
  exit 1
fi

conf="/etc/wsl.conf"
timestamp="$(date +%Y%m%d_%H%M%S)"

# 기존 설정 백업
if [[ -f "$conf" ]]; then
  cp "$conf" "${conf}.bak.${timestamp}"
  echo "기존 wsl.conf 백업: ${conf}.bak.${timestamp}"
fi

cat > "$conf" <<'EOF'
[boot]
# systemd 사용 (WSL 1은 미지원)
systemd=true

[network]
# WSL이 /etc/resolv.conf를 자동 생성하지 않도록 함
generateResolvConf=false

[interop]
# Windows PATH를 WSL에 추가
appendWindowsPath=true

[automount]
# 드라이브 자동 마운트 시 권한/메타데이터 유지
options = "metadata,umask=22,fmask=11"
mountFsTab = true
EOF

# 선택: resolv.conf 기본값 설정 (필요 없으면 주석 처리)
if [[ ! -f /etc/resolv.conf ]]; then
  cat > /etc/resolv.conf <<'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF
  chmod 644 /etc/resolv.conf
  echo "/etc/resolv.conf 기본 DNS 설정 완료"
fi

echo "wsl.conf 적용 완료. Windows에서 'wsl.exe --shutdown' 후 WSL을 다시 시작하세요."
