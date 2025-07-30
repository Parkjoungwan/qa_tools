import subprocess
import time
import ctypes
import objc
import os
from Cocoa import NSBundle

# 📍 현재 Python 스크립트의 경로를 기준으로 상대 경로 계산
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCK_SCRIPT = os.path.join(BASE_DIR, "../../Scripts/screenBrightnessDown.sh")
UNLOCK_SCRIPT = os.path.join(BASE_DIR, "../../Scripts/screenBrightnessUp.sh")

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
        if now_locked:
            print("🔒 화면 잠금 감지됨. on_lock.sh 실행.")
            subprocess.run(["sh", LOCK_SCRIPT])
        else:
            print("🔓 화면 잠금 해제 감지됨. on_unlock.sh 실행.")
            subprocess.run(["sh", UNLOCK_SCRIPT])
        was_locked = now_locked

