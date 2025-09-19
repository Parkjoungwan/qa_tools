from pathlib import Path
import platformdirs
import logging

APP_NAME = "UIFlowRecorder"
APP_AUTHOR = "Gemini"

# Use platformdirs to handle cross-platform data paths
USER_DATA_DIR = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
USER_CONFIG_DIR = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))

# Ensure directories exist
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# --- File Paths ---
DATA_FILE = USER_DATA_DIR / "flow_data.json"
DEVICE_PROFILES_FILE = USER_CONFIG_DIR / "device_profiles.json"

# --- Project-relative Paths (for things that should stay with the project) ---
PROJECT_ROOT = Path(__file__).parent
IMAGES_DIR = PROJECT_ROOT / "images"
SESSIONS_DIR = PROJECT_ROOT / "sessions"

# --- Matching Thresholds ---
SIMILARITY_THRESHOLD = 0.85
TEMPLATE_MATCH_THRESHOLD = 0.75

# --- Exploration ---
MAX_EXPLORATION_DEPTH = 10
MAX_EXPLORATION_TIME_SEC = 180 # 3 minutes
MIN_EVENT_DELAY_SEC = 0.20  # 최소 이벤트 대기(초): 리플레이 재현성 보강

# --- Constants ---
MAX_REF_IMAGES = 10
REPLAY_SEGMENT_GAP_SEC = 1.0 # Time to wait between transition segments
VERIFY_ARRIVAL_TIMEOUT_SEC = 5 # Max time to wait for arrival verification
VERIFY_ARRIVAL_INTERVAL_SEC = 0.5 # Interval between verification attempts

# --- Safety ---
SENSITIVE_KEYWORDS = {
    'en': (
        "delete", "remove", "erase", "pay", "purchase", "buy", "checkout", 
        "logout", "sign out", "exit", "quit", "confirm"
    ),
    'ko': (
        "삭제", "제거", "지우기", "결제", "구매", "구입", "체크아웃",
        "로그아웃", "로그 아웃", "종료", "나가기", "확인", "동의", "승인"
    )
}
BACK_BUTTON_KEYWORDS = {
    'en': ("back", "close", "cancel", "done"),
    'ko': ("뒤로", "이전", "닫기", "취소", "완료", "돌아가기")
}

# --- Logging ---
LOG_FORMAT = "[%(asctime)s][%(levelname)s][%(name)s] %(message)s"
LOG_LEVEL = logging.INFO
