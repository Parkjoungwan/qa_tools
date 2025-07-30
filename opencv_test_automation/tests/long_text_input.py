# tests/long_text_input.py
"""
긴 텍스트 입력 테스트 v4
────────────────────────────────────────────────────────
• UTF-8 바이트 길이 80 이하로 자동 조각
• 입력 불가 문자(7-bit ASCII 밖)는 안전한 ‘-’ 로 치환
"""

import os, time, re
from dotenv import load_dotenv
from utils import adb_utils

### 1) 대상 기기 지정 (.env) ##############################################
load_dotenv()
serial = os.getenv("ADB_SERIAL") or os.getenv("ANDROID_SERIAL")
if serial:
    adb_utils.set_device(serial)
    print(f"📱  대상 기기: {serial}")

### 2) 620+ 자 테스트 본문 ##################################################
TEXT = (
    "This demonstration paragraph is intentionally verbose and expansive so that it "
    "comfortably exceeds the five-hundred-character mark required for a more exhaustive "
    "test. When you automate mobile applications it is surprisingly common to discover "
    "that very long strings produce corner-case behaviour, especially when they must be "
    "transmitted through shell commands rather than typed directly on the virtual "
    "keyboard. Because the Android Debug Bridge interprets each contiguous sequence of "
    "text as a single token, spaces must be encoded with the percent-s sequence. "
    "Developers who overlook this typically encounter baffling truncations, lost words, "
    "or even inexplicable failures that only appear when the payload reaches a specific "
    "length on older operating-system builds or under vendor-specific customisations. "
    "Splitting the content into manageable segments is therefore the safest strategy. "
    "It ensures that the upper bound imposed by the command parser is never exceeded "
    "and also allows granular progress feedback — very handy when debugging UI flows on "
    "remote CI devices that may exhibit higher latency. This example demonstrates how "
    "to simulate typing a paragraph of text for testing. It uses only ADB shell "
    "commands and should be runnable on a connected device."
)

### 3) 안전 문자 치환 + 80바이트 이하 블록 나누기 ##########################
MAX_BYTES = 80          # 경험상 100 미만이 안전
PAUSE      = 0.2        # 블록 사이 딜레이

# input text 가 허용하는 문자는 [A-Za-z0-9_.-] 와 %s·%p 등만 확실
SAFE_CHR = re.compile(r"[^A-Za-z0-9\.\-\_\%s]")

def safe_word(word: str) -> str:
    """허용되지 않는 문자는 '-' 로 바꿔 준다."""
    return SAFE_CHR.sub("-", word)

def chunks_utf8(words: list[str]):
    buff, size = [], 0
    for w in words:
        w = safe_word(w)
        extra = len(w.encode()) + (2 if buff else 0)  # %s 추가
        if size + extra > MAX_BYTES:
            yield "%s".join(buff)
            buff, size = [], 0
        buff.append(w)
        size += extra
    if buff:
        yield "%s".join(buff)

### 4) 실행 ###############################################################
def run_long_text_input():
    words = TEXT.split()
    for idx, block in enumerate(chunks_utf8(words), 1):
        print(f"⌨️  블록 {idx}: {len(block.encode())} bytes")
        adb_utils.input_text(block)
        time.sleep(PAUSE)

if __name__ == "__main__":
    import time
    start = time.time()
    try:
        run_long_text_input()
        print(f"✅  완료! 소요 {time.time()-start:.2f}s")
    except Exception as e:
        print(f"❌  실패: {e} ({time.time()-start:.2f}s)")
