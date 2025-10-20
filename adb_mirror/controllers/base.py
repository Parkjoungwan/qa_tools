from abc import ABC, abstractmethod
from subprocess import Popen
from typing import Tuple, Optional

class DeviceController(ABC):
    """An abstract base class for device interaction, defining a common interface."""

    def __init__(self, serial: str):
        self.serial = serial
        self.mirror_process: Optional[Popen] = None

    @abstractmethod
    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """Returns the device's screen resolution (width, height)."""
        raise NotImplementedError

    @abstractmethod
    def start_mirror(
        self, window_title: str, rect: Tuple[int, int, int, int], no_control: bool = False
    ) -> Optional[Popen]:
        """Starts the screen mirroring process and returns the subprocess object."""
        raise NotImplementedError

    def stop_mirror(self) -> None:
        """Stops the screen mirroring process."""
        if self.mirror_process and self.mirror_process.poll() is None:
            print(f"Terminating mirror process for {self.serial}...")
            self.mirror_process.terminate()
            try:
                self.mirror_process.wait(timeout=5)
            except Exception:
                self.mirror_process.kill()

    @abstractmethod
    def tap(self, x: int, y: int) -> None:
        """Simulates a tap at the given coordinates."""
        raise NotImplementedError

    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        """Simulates a swipe from (x1, y1) to (x2, y2)."""
        raise NotImplementedError

    @abstractmethod
    def text(self, text_input: str) -> None:
        """Injects a string of text."""
        raise NotImplementedError
