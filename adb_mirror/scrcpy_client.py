import socket
import struct
import time

# Based on https://github.com/Genymobile/scrcpy/blob/master/app/src/control_msg.h
CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT = 2

# Based on https://github.com/Genymobile/scrcpy/blob/master/app/src/android/input_manager.h
AMOTION_EVENT_ACTION_DOWN = 0
AMOTION_EVENT_ACTION_UP = 1
AMOTION_EVENT_ACTION_MOVE = 2
AMOTION_EVENT_BUTTON_PRIMARY = 1
POINTER_ID_GENERIC_FINGER = -1 # 0xffffffffffffffff

class ScrcpyClient:
    """A client to send control messages to a scrcpy-server instance."""

    def __init__(self, device_width: int, device_height: int):
        self.device_width = device_width
        self.device_height = device_height
        self.control_socket = None

    def connect(self, port: int = 27183) -> None:
        """Connect to the scrcpy-server control socket."""
        try:
            self.control_socket = socket.create_connection(("127.0.0.1", port), timeout=1.0)
            # Disable Nagle's algorithm for low latency
            self.control_socket.settimeout(1.0)
            self.control_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception as e:
            print(f"Failed to connect to scrcpy control socket on port {port}: {e}")
            self.control_socket = None
            raise

    def disconnect(self) -> None:
        """Disconnect from the control socket."""
        if self.control_socket:
            self.control_socket.close()
            self.control_socket = None

    def _send_control_msg(self, msg_bytes: bytes) -> None:
        if not self.control_socket:
            raise ConnectionError("Not connected to scrcpy-server")
        self.control_socket.sendall(msg_bytes)

    def _build_touch_message(self, x: int, y: int, action: int) -> bytes:
        """Build a binary touch event message according to the scrcpy protocol."""
        # struct format: > B B q i i H H H I
        # >: big-endian
        # B: unsigned char (1) -> type
        # B: unsigned char (1) -> action
        # q: long long (8)     -> pointerId
        # i: int (4)           -> x
        # i: int (4)           -> y
        # H: unsigned short (2) -> width
        # H: unsigned short (2) -> height
        # H: unsigned short (2) -> pressure
        # I: unsigned int (4)   -> buttons
        return struct.pack(
            ">BBqiiHHHI",
            CONTROL_MSG_TYPE_INJECT_TOUCH_EVENT,
            action,
            POINTER_ID_GENERIC_FINGER,
            int(x),
            int(y),
            self.device_width,
            self.device_height,
            0xFFFF,  # pressure
            AMOTION_EVENT_BUTTON_PRIMARY,
        )

    def touch(self, x: int, y: int, action: int) -> None:
        """Send a single touch event."""
        msg = self._build_touch_message(x, y, action)
        self._send_control_msg(msg)

    def tap(self, x: int, y: int) -> None:
        """Simulate a tap by sending a DOWN followed by an UP event."""
        self.touch(x, y, AMOTION_EVENT_ACTION_DOWN)
        # A small delay is often necessary for the server to process the DOWN event
        # before receiving the UP event. 20ms is usually safe.
        time.sleep(0.02)
        self.touch(x, y, AMOTION_EVENT_ACTION_UP)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 200) -> None:
        """Simulate a swipe by sending a sequence of touch events."""
        self.touch(x1, y1, AMOTION_EVENT_ACTION_DOWN)

        steps = int(duration_ms / 10) or 1
        delay_per_step = duration_ms / 1000 / steps

        for i in range(1, steps + 1):
            t = i / steps
            x = int(x1 + (x2 - x1) * t)
            y = int(y1 + (y2 - y1) * t)
            self.touch(x, y, AMOTION_EVENT_ACTION_MOVE)
            time.sleep(delay_per_step)

        self.touch(x2, y2, AMOTION_EVENT_ACTION_UP)
