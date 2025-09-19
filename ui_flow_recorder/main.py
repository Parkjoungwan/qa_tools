import sys
import argparse
import subprocess
import time
import logging
from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication

from config import SESSIONS_DIR, IMAGES_DIR, LOG_FORMAT, LOG_LEVEL
from adb_utils import get_device_serials
from recorder import FlowRecorder
from file_io import save_flow_data, load_flow_data

def write_report(session_dir, session_ts, stats, flow_data=None):
    stats.end_time = time.time()
    stats.session_duration = round(stats.end_time - stats.start_time, 2)

    report_path = session_dir / "report.md"
    with open(report_path, "w") as f:
        f.write(f"# UI Flow Report ({session_ts})\n\n")
        f.write("## Session Summary\n")
        f.write("| Metric | Value |\n")
        f.write("|---|---|")
        f.write(f"| Session Duration | {stats.session_duration}s |\n")
        f.write(f"| Screens Found | {stats.screens_found} |\n")
        f.write(f"| Transitions Found | {stats.transitions_found} |\n")
        if stats.validation_avg_error is not None:
            f.write(f"| Validation Avg Error | {stats.validation_avg_error:.2f} px |\n")
            f.write(f"| Validation Max Error | {stats.validation_max_error:.2f} px |\n")
        if flow_data:
            legacy_cnt = sum(1 for t in flow_data.transitions if getattr(t, "legacy", False))
            f.write(f"| Legacy Transitions | {legacy_cnt} |\n")

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="UI Flow Recorder using ADB and OpenCV.")
    parser.add_argument("--serial", help="The device serial to connect to.")
    parser.add_argument("--run_tag", default="run", help="A tag for the session directory name.")
    args = parser.parse_args()

    serials = get_device_serials()
    if not serials:
        print("No ADB devices found or DEVICE_SERIAL not set in .env")
        sys.exit(1)

    device_serial = args.serial or serials[0]

    # Ensure all necessary directories exist at startup
    SESSIONS_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)

    session_ts = time.strftime("%Y%m%d_%H%M%S")
    session_dir = SESSIONS_DIR / f"{session_ts}_{args.run_tag}"
    session_dir.mkdir()

    # Setup logging
    log_file = session_dir / "session.log"
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ])
    logger = logging.getLogger(__name__)

    (session_dir / "report.md").write_text(f"# UI Flow Report ({session_ts})\n\n*Session in progress...*")

    logger.info(f"Session artifacts will be saved to: {session_dir}")
    logger.info(f"Using device: {device_serial}")

    app = QApplication(sys.argv)
    recorder = None
    try:
        recorder = FlowRecorder(serial=device_serial, session_dir=session_dir)
    except RuntimeError as e:
        logger.error(f"Error initializing recorder: {e}")
        sys.exit(1)

    scrcpy_proc = subprocess.Popen([
        "scrcpy", "--serial", device_serial, "--no-control", "--no-audio",
        "--window-title", f"scrcpy - {device_serial}", "--window-x", "0", "--window-y", "0",
        "--window-width", str(recorder.viewer_w), "--window-height", str(recorder.viewer_h),
        "--window-borderless", "--max-size", "960"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)

    time.sleep(2)
    recorder.show()

    exit_code = 0
    try:
        exit_code = app.exec_()
    finally:
        logger.info("Cleaning up...")
        scrcpy_proc.terminate()
        scrcpy_proc.wait()
        if recorder:
            save_flow_data(recorder.flow_data)
            write_report(session_dir, session_ts, recorder.session_stats, flow_data=recorder.flow_data)
        logger.info("Flow data and report saved. Exiting.")

    sys.exit(exit_code)

if __name__ == "__main__":
    main()
