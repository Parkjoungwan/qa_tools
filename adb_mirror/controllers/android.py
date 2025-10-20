import subprocess
from typing import Tuple, Optional, List

from .base import DeviceController


class AndroidController(DeviceController):
    """Controls an Android device using adb and scrcpy."""

    def __init__(self, serial: str):
        super().__init__(serial)
        self.device_res: Optional[Tuple[int, int]] = self.get_resolution()

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """Returns the device's screen resolution (width, height)."""
        try:
            output = subprocess.check_output(
                ["adb", "-s", self.serial, "shell", "wm", "size"]
            ).decode()
            w, h = map(int, output.strip().split(": ")[-1].split("x"))
            # Ensure width is greater than height for landscape orientation
            return (w, h) if w > h else (h, w)
        except Exception as e:
            print(f"Error getting resolution for {self.serial}: {e}")
            return None

    def start_mirror(
        self, window_title: str, rect: Tuple[int, int, int, int], no_control: bool = False
    ) -> Optional[subprocess.Popen]:
        """Starts the scrcpy mirroring process."""
        x, y, w, h = rect
        common_args = [
            "--serial", self.serial,
            "--window-title", window_title,
            "--window-x", str(x),
            "--window-y", str(y),
            "--window-width", str(w),
            "--window-height", str(h),
            "--no-audio",
            "--window-borderless",
            "--max-size", "960", # TODO: Make this configurable
        ]
        if no_control:
            common_args.append("--no-control")

        try:
            print(f"Starting scrcpy for {self.serial}...")
            self.mirror_process = subprocess.Popen(
                ["scrcpy"] + common_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            return self.mirror_process
        except FileNotFoundError:
            print("Error: 'scrcpy' command not found. Make sure it is installed and in your PATH.")
            return None
        except Exception as e:
            print(f"Error starting scrcpy for {self.serial}: {e}")
            return None

    def tap(self, x: int, y: int) -> None:
        """Simulates a tap at the given coordinates using adb."""
        subprocess.run(["adb", "-s", self.serial, "shell", "input", "tap", str(x), str(y)])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        """Simulates a swipe using adb."""
        subprocess.run([
            "adb", "-s", self.serial, "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2), str(duration_ms)
        ])

    def text(self, text_input: str) -> None:
        """Injects a string of text using adb."""
        # Using subprocess.run with shell=True for quoting is tricky and can be a security risk.
        # A direct list of args is safer.
        subprocess.run(["adb", "-s", self.serial, "shell", "input", "text", text_input])


def get_android_devices() -> List[str]:
    """Returns a list of connected Android device serials."""
    try:
        output = subprocess.check_output(["adb", "devices"]).decode()
        lines = output.strip().splitlines()[1:]
        return [line.split()[0] for line in lines if line.strip().endswith("device")]
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
