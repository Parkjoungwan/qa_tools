import subprocess
import time
import ctypes
import objc
import os
from Cocoa import NSBundle

def get_device_serials():
    """현재 연결된 모든 adb 기기의 시리얼 번호 리스트를 반환합니다."""
    try:
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
        devices = result.stdout.strip().split('\n')[1:]
        return [line.split('\t')[0] for line in devices if line]
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("adb 명령을 실행할 수 없거나 기기가 연결되지 않았습니다.")
    return []

def set_brightness(serial, value):
    """지정된 기기의 화면 밝기를 설정합니다."""
    if serial:
        subprocess.run(['adb', '-s', serial, 'shell', 'settings', 'put', 'system', 'screen_brightness', str(value)])

# macOS 화면 잠금 여부 확인 함수
def is_screen_locked():
    bundle = NSBundle.bundleWithIdentifier_('com.apple.frameworks.CoreGraphics')
    functions = [('CGSessionCopyCurrentDictionary', b'@')]
    objc.loadBundleFunctions(bundle, globals(), functions)
    session_dict = CGSessionCopyCurrentDictionary()
    
    if session_dict is None:
        return False

    return session_dict.get("CGSSessionScreenIsLocked", 0) == 1

# 🔁 상태 감지 루프
was_locked = is_screen_locked()

while True:
    time.sleep(1)

    now_locked = is_screen_locked()

    if now_locked != was_locked:
        serials = get_device_serials()
        if serials:
            for serial in serials:
                if now_locked:
                    print(f"🔒 화면 잠금 감지됨. [{serial}] 화면 밝기를 낮춥니다.")
                    set_brightness(serial, 10)
                else:
                    print(f"🔓 화면 잠금 해제 감지됨. [{serial}] 화면 밝기를 높입니다.")
                    set_brightness(serial, 100)
        was_locked = now_locked

