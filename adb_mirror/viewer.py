import time
import threading
from typing import List, Optional, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit

from controllers.base import DeviceController


class MultiViewer(QWidget):
    def __init__(
        self,
        controllers: List[DeviceController],
        win_name: str = "Device Mirror",
        log_fn=None,
        viewer_width_per_device: int = 1200,
        viewer_height: int = 750,
    ):
        super().__init__()
        self.controllers = controllers
        self.log_fn = log_fn
        self.viewer_w, self.viewer_h = viewer_width_per_device, viewer_height

        self.setWindowTitle(win_name)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.viewer_w * len(self.controllers), self.viewer_h)
        self.move(0, 0)
        self.setFocusPolicy(Qt.StrongFocus)

        self._drag_controller: Optional[DeviceController] = None
        self._drag_start: Optional[Tuple[int, int]] = None
        self._drag_time: Optional[float] = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        for i, controller in enumerate(self.controllers):
            pen = QPen(QColor(0, 255, 0))
            pen.setWidth(5)
            p.setPen(pen)
            p.drawRect(i * self.viewer_w, 0, self.viewer_w, self.viewer_h)
            p.setPen(QColor(255, 255, 255))
            p.drawText(i * self.viewer_w + 20, 40, f"[{controller.serial}] click/drag, W for text")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            QApplication.quit()
        elif e.key() == Qt.Key_W:
            self.handle_text_input()
        else:
            super().keyPressEvent(e)

    def handle_text_input(self):
        if not self.controllers:
            return
        
        serials = [c.serial for c in self.controllers]
        serial, ok = QInputDialog.getItem(self, "Select Device", "Enter text on:", serials, 0, False)
        if not ok or not serial:
            return

        text, ok = QInputDialog.getText(self, "Input Text", f"Enter text for {serial}:", QLineEdit.Normal, "")
        if ok and text:
            controller = next((c for c in self.controllers if c.serial == serial), None)
            if controller:
                threading.Thread(target=controller.text, args=(text,), daemon=True).start()
                if self.log_fn:
                    self.log_fn("text", serial, text)

    def mousePressEvent(self, e):
        if e.button() not in (Qt.LeftButton, Qt.RightButton):
            return
        
        mapped_info = self._map_to_device(e.x(), e.y())
        if mapped_info is None:
            return
        
        controller, dev_x, dev_y = mapped_info
        if e.button() == Qt.LeftButton:
            self._drag_controller = controller
            self._drag_start = (dev_x, dev_y)
            self._drag_time = time.perf_counter()
        # Right-click could be used for other actions, e.g., back button
        # else:
        #     if self.log_fn: self.log_fn("cap", serial)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or self._drag_controller is None:
            return

        mapped_info = self._map_to_device(e.x(), e.y())
        if mapped_info is None:
            self._drag_controller = None
            return

        controller, end_x, end_y = mapped_info
        start_x, start_y = self._drag_start
        duration_ms = int((time.perf_counter() - self._drag_time) * 1000)

        # Check if it was a tap or a swipe
        if abs(end_x - start_x) < 5 and abs(end_y - start_y) < 5:
            # TAP
            threading.Thread(target=controller.tap, args=(end_x, end_y), daemon=True).start()
            if self.log_fn:
                self.log_fn("tap", controller.serial, end_x, end_y)
        else:
            # SWIPE
            duration_ms = max(duration_ms, 50)
            threading.Thread(target=controller.swipe, args=(start_x, start_y, end_x, end_y, duration_ms), daemon=True).start()
            if self.log_fn:
                self.log_fn("swipe", controller.serial, start_x, start_y, end_x, end_y, duration_ms)
        
        self._drag_controller = None

    def _map_to_device(self, x: int, y: int) -> Optional[Tuple[DeviceController, int, int]]:
        for i, controller in enumerate(self.controllers):
            left_bound = i * self.viewer_w
            if not (left_bound <= x < left_bound + self.viewer_w):
                continue

            if not controller.device_res:
                return None
            
            dev_w, dev_h = controller.device_res

            # Calculate the scaled dimensions and offset of the mirrored screen
            scale = self.viewer_h / dev_h
            effective_w = int(dev_w * scale)
            offset_x = (self.viewer_w - effective_w) // 2

            # Check if the click is within the bounds of the scaled screen
            if not (offset_x <= x - left_bound < offset_x + effective_w):
                return None

            # Convert window coordinates to device coordinates
            device_x = int((x - left_bound - offset_x) * dev_w / effective_w)
            device_y = int(y * dev_h / self.viewer_h)
            return controller, device_x, device_y
        
        return None