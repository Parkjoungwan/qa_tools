import time
import math
import threading
import logging
import re
from typing import List, Optional, Tuple, Dict
from datetime import datetime
from collections import deque

import cv2
import numpy as np
try:
    import easyocr
except ImportError:
    easyocr = None

from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QRect, QMetaObject, Q_ARG
from PyQt5.QtGui import QPainter, QColor, QPen
from PyQt5.QtWidgets import QWidget, QApplication, QInputDialog, QLineEdit
from skimage.metrics import structural_similarity as ssim
from pathlib import Path

import adb_utils
from config import IMAGES_DIR, SIMILARITY_THRESHOLD, MAX_REF_IMAGES, SENSITIVE_KEYWORDS, BACK_BUTTON_KEYWORDS, MAX_EXPLORATION_DEPTH, MAX_EXPLORATION_TIME_SEC, MIN_EVENT_DELAY_SEC
from diagram import DiagramWidget
from file_io import save_flow_data, load_flow_data
from models import TouchEvent, Screen, Transition, SessionStats
from transform import DisplayTransform
from detector import Uiautomator2Detector

logger = logging.getLogger(__name__)

def replay_touch_events(serial: str, events: List[Dict], on_finish=None):
    try:
        if not events or events[0].get("__legacy__"): 
            logger.warning("Skipping replay of legacy or empty transition.")
            if callable(on_finish): on_finish()
            return

        transform = DisplayTransform(serial)

        logger.info(f"Replaying events on device with resolution {transform.current_w}x{transform.current_h} and orientation {transform.orientation}")
        start_time = time.perf_counter()
        for event in sorted(events, key=lambda e: e['time']):
            event_time = event['time']
            delay = max((start_time + event_time) - time.perf_counter(), MIN_EVENT_DELAY_SEC)
            if delay > 0:
                time.sleep(delay)

            transform.update(force=True)

            if event['type'] == 'tap':
                x, y = transform.from_natural_normalized(event['u'], event['v'])
                logger.debug(f"Replaying tap: u,v=({event['u']:.3f}, {event['v']:.3f}) -> x,y=({x}, {y})")
                adb_utils.adb_tap(serial, x, y)
            elif event['type'] == 'swipe':
                x1, y1 = transform.from_natural_normalized(event['u1'], event['v1'])
                x2, y2 = transform.from_natural_normalized(event['u2'], event['v2'])
                logger.debug(f"Replaying swipe: u,v=({event['u1']:.3f}, {event['v1']:.3f} -> {event['u2']:.3f}, {event['v2']:.3f}) -> x,y=({x1},{y1} -> {x2},{y2})")
                adb_utils.adb_swipe(serial, x1, y1, x2, y2, event['duration'])
    finally:
        if callable(on_finish):
            on_finish()

class FlowRecorder(QWidget):
    def __init__(self, serial: str, session_dir, win_name: str = "UI Flow Recorder"):
        super().__init__()
        self.serial = serial
        self.session_dir = session_dir
        self.transform = DisplayTransform(serial)
        self.device_w, self.device_h = self.transform.current_w, self.transform.current_h
        self.flow_data = load_flow_data()
        self.u2_device = adb_utils.connect_uiautomator(self.serial)
        self.detector = Uiautomator2Detector(self.u2_device) if self.u2_device else None
        self.ocr_reader = easyocr.Reader(['en', 'ko']) if easyocr else None
        self.session_stats = SessionStats()

        self.viewer_w, self.viewer_h = 1200, 750
        self.setWindowTitle(win_name)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.viewer_w, self.viewer_h)
        self.move(0, 0)
        self.setFocusPolicy(Qt.StrongFocus)

        self.is_path_recording = False
        self.path_start_screen_id = None
        self.path_start_time = None
        self.is_event_recording = False
        self.recorded_events = []
        self.drag_start_pos = None
        self.drag_start_time = None
        self.is_debug_overlay_visible = False
        self.is_exploring = False
        self.exploration_thread = None
        self.exploration_stop_event = threading.Event()

        self.adb_executing = False
        self.status_message = ""
        self.diagram_widget = None

    def extract_text_from_image(self, image: np.ndarray) -> str:
        if not self.ocr_reader:
            return ""
        try:
            results = self.ocr_reader.readtext(image, detail=0, paragraph=True)
            return " ".join(results).lower()
        except Exception as e:
            logger.error(f"Failed to extract text with EasyOCR: {e}")
            return ""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen_color = QColor(0, 255, 0)
        if self.is_path_recording: pen_color = QColor(255, 0, 0)
        if self.is_exploring: pen_color = QColor(0, 0, 255)
        pen = QPen(pen_color); pen.setWidth(5)
        p.setPen(pen); p.drawRect(0, 0, self.viewer_w - 1, self.viewer_h - 1)
        p.setPen(QColor(255, 255, 255))
        p.drawText(20, 40, f"Device: {self.serial}")
        p.drawText(20, 60, "R: Record, C: Capture, G: Diagram, E: Explore, D: Debug, V: Validate, ESC: Quit")
        if self.is_path_recording:
            start_screen = self.flow_data.screens.get(self.path_start_screen_id)
            start_screen_name = start_screen.name if start_screen else "UNKNOWN"
            p.drawText(20, 80, f"[RECORDING] From: '{start_screen_name}'. Press 'C' to end.")
        if self.is_exploring:
            p.drawText(20, 80, "[EXPLORING] Press 'E' to stop.")
        if self.status_message: p.drawText(20, 100, self.status_message)
        if self.adb_executing: p.drawText(20, self.viewer_h - 20, "Executing ADB...")

        if self.is_debug_overlay_visible:
            self.draw_debug_overlay(p)

    def draw_debug_overlay(self, p: QPainter):
        scale_w = self.viewer_w / self.device_w
        scale_h = self.viewer_h / self.device_h
        scale = min(scale_w, scale_h)
        eff_w = int(self.device_w * scale)
        eff_h = int(self.device_h * scale)
        off_x = (self.viewer_w - eff_w) // 2
        off_y = (self.viewer_h - eff_h) // 2

        l, t, r, b = self.transform.stable_insets
        safe_rect_viewer = QRect(
            off_x + int(l * scale),
            off_y + int(t * scale),
            int((self.device_w - l - r) * scale),
            int((self.device_h - t - b) * scale)
        )
        p.setPen(QPen(QColor(255, 0, 0, 180), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(safe_rect_viewer)

        p.setPen(QColor(255, 255, 0, 200))
        font = p.font(); font.setPointSize(10); p.setFont(font)
        info_lines = [
            f"Orientation: {self.transform.orientation}",
            f"Device Res: {self.device_w}x{self.device_h}",
            f"Insets (L,T,R,B): {self.transform.stable_insets}",
            f"Safe Area (x,y,w,h): {self.transform.safe_area_x, self.transform.safe_area_y, self.transform.safe_area_w, self.transform.safe_area_h}"
        ]
        for i, line in enumerate(info_lines):
            p.drawText(20, self.viewer_h - 80 + i * 15, line)

    def keyPressEvent(self, e):
        key_map = {Qt.Key_Escape: QApplication.quit, Qt.Key_R: self.start_path_recording, 
                   Qt.Key_C: self.capture_and_end_path, Qt.Key_G: self.show_diagram}
        if (action := key_map.get(e.key())):
            action()
        elif e.key() == Qt.Key_D:
            self.is_debug_overlay_visible = not self.is_debug_overlay_visible
            self.update()
        elif e.key() == Qt.Key_V:
            self.run_validation_test()
        elif e.key() == Qt.Key_E:
            self.toggle_exploration()
        else: 
            super().keyPressEvent(e)

    def _map_to_device(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        self.transform.update()
        self.device_w, self.device_h = self.transform.current_w, self.transform.current_h

        scale_w = self.viewer_w / self.device_w
        scale_h = self.viewer_h / self.device_h
        scale = min(scale_w, scale_h)

        eff_w = int(self.device_w * scale)
        eff_h = int(self.device_h * scale)

        off_x = (self.viewer_w - eff_w) // 2
        off_y = (self.viewer_h - eff_h) // 2

        if not (off_x <= x < off_x + eff_w and off_y <= y < off_y + eff_h):
            return None

        device_x = int((x - off_x) / scale)
        device_y = int((y - off_y) / scale)
        
        return device_x, device_y

    def find_pointer_location_marker(self, image: np.ndarray) -> Optional[Tuple[int, int]]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        lower_blue = np.array([100, 150, 150])
        upper_blue = np.array([140, 255, 255])
        mask = cv2.inRange(hsv, lower_blue, upper_blue)

        if np.sum(mask) < 20: return None

        x_proj = np.sum(mask, axis=0)
        y_proj = np.sum(mask, axis=1)

        x = np.argmax(x_proj)
        y = np.argmax(y_proj)

        if x_proj[x] > 0 and y_proj[y] > 0:
            return x, y
        return None

    def run_validation_test(self):
        self.set_status("Starting validation test...", 10000)
        QApplication.processEvents()

        test_points_uv = [
            (0.2, 0.2), (0.5, 0.2), (0.8, 0.2),
            (0.2, 0.5), (0.5, 0.5), (0.8, 0.5),
            (0.2, 0.8), (0.5, 0.8), (0.8, 0.8),
        ]
        errors = []
        
        adb_utils.set_developer_option(self.serial, "pointer_location", 1)
        time.sleep(0.5)

        try:
            for i, (u, v) in enumerate(test_points_uv):
                self.transform.update(force=True)
                target_px, target_py = self.transform.from_natural_normalized(u, v)
                
                self.set_status(f"Testing point {i+1}/{len(test_points_uv)} at ({target_px}, {target_py})...", 3000)
                QApplication.processEvents()

                adb_utils.adb_tap(self.serial, target_px, target_py)
                time.sleep(0.2)
                
                img = adb_utils.adb_capture(self.serial)
                if img is None: 
                    logger.warning(f"Failed to capture screen for point ({u:.2f}, {v:.2f})"); continue

                marker_pos = self.find_pointer_location_marker(img)
                if marker_pos is None: 
                    logger.warning(f"Could not find marker for point ({u:.2f}, {v:.2f})"); continue

                mx, my = marker_pos
                error = math.sqrt((target_px - mx)**2 + (target_py - my)**2)
                errors.append(error)
                logger.info(f"Point ({u:.2f}, {v:.2f}): Target=({target_px},{target_py}), Found=({mx},{my}), Error={error:.2f}px")

        finally:
            adb_utils.set_developer_option(self.serial, "pointer_location", 0)
            self.set_status("Validation finished.", 5000)

        if errors:
            self.session_stats.validation_avg_error = np.mean(errors)
            self.session_stats.validation_max_error = np.max(errors)
            report = (
                f"\n\n## Transform Validation Report ({datetime.now().isoformat()})\n"
                f"- Points Tested: {len(errors)}/{len(test_points_uv)}\n"
                f"- Average Error: {self.session_stats.validation_avg_error:.2f} px\n"
                f"- Max Error: {self.session_stats.validation_max_error:.2f} px\n"
                f"- Std Dev: {np.std(errors):.2f} px\n"
            )
            logger.info(report)
            with open(self.session_dir / "report.md", "a") as f:
                f.write(report)
        else:
            logger.warning("Validation test could not be completed.")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.is_event_recording and (coords := self._map_to_device(e.pos().x(), e.pos().y())):
            self.drag_start_pos = coords
            self.drag_start_time = time.perf_counter()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not (px_py := self._map_to_device(e.pos().x(), e.pos().y())): return
        px, py = px_py

        if self.is_event_recording and self.drag_start_pos:
            self.transform.update()
            u, v = self.transform.to_natural_normalized(px, py)
            
            sx, sy = self.drag_start_pos
            su, sv = self.transform.to_natural_normalized(sx, sy)

            duration_ms = int((time.perf_counter() - self.drag_start_time) * 1000)
            event_time = time.perf_counter() - self.path_start_time

            if abs(px - sx) < 5 and abs(py - sy) < 5:
                event = TouchEvent(type="tap", u=round(u, 4), v=round(v, 4), time=round(event_time, 4))
                adb_utils.adb_tap(self.serial, px, py)
            else:
                event = TouchEvent(type="swipe", u1=round(su, 4), v1=round(sv, 4), u2=round(u, 4), v2=round(v, 4), duration=max(duration_ms, 50), time=round(event_time, 4))
                adb_utils.adb_swipe(self.serial, sx, sy, px, py, max(duration_ms, 50))

            self.recorded_events.append(event)
            logger.debug(f"Event recorded: {event}")
            self.drag_start_pos = self.drag_start_time = None
        else:
            adb_utils.adb_tap(self.serial, px, py)

    def start_path_recording(self):
        if self.is_path_recording: self.set_status("Already recording. Press 'C' to complete."); return
        self.set_status("Capturing start screen..."); self.adb_executing = True; self.update(); QApplication.processEvents()
        self.transform.update(force=True)
        screen_id, _ = self.capture_and_identify_screen()
        if screen_id:
            self.is_path_recording = self.is_event_recording = True
            self.path_start_screen_id = screen_id
            self.path_start_time = time.perf_counter()
            self.recorded_events = []
            start_screen = self.flow_data.screens.get(screen_id)
            start_screen_name = start_screen.name if start_screen else "UNKNOWN"
            self.set_status(f"Path started from '{start_screen_name}'. Navigate and press 'C'.")
        else: self.set_status("Failed to identify start screen.")
        self.adb_executing = False; self.update()

    def capture_and_end_path(self):
        if not self.is_path_recording: self.set_status("Not recording. Press 'R' to start."); return
        self.is_event_recording = False
        self.set_status("Capturing destination screen..."); self.adb_executing = True; self.update(); QApplication.processEvents()
        self.transform.update(force=True)
        to_screen_id, _ = self.capture_and_identify_screen()
        if to_screen_id:
            from_screen_id = self.path_start_screen_id
            self.check_and_add_transition(from_screen_id, to_screen_id, self.recorded_events)
            from_screen = self.flow_data.screens.get(from_screen_id)
            to_screen = self.flow_data.screens.get(to_screen_id)
            from_name = from_screen.name if from_screen else "?"
            to_name = to_screen.name if to_screen else "?"
            self.set_status(f"Path recorded: {from_name} -> {to_name}")
            if self.diagram_widget: self.diagram_widget.set_current_screen_id(to_screen_id, center=True)
        else: self.set_status("Failed to identify destination screen.")
        self.path_start_screen_id = None
        self.is_path_recording = False
        self.adb_executing = False; self.update()

    def _ssim_match(self, ref_img_gray: np.ndarray, new_img_gray: np.ndarray) -> float:
        try: return float(ssim(ref_img_gray, new_img_gray, full=True)[0])
        except Exception: return 0.0

    def _frame_to_gray(self, frame_bgr: np.ndarray, size: Tuple[int, int]) -> Optional[np.ndarray]:
        try: return cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), size)
        except Exception: return None

    def match_existing_screen(self, frame_bgr: np.ndarray, expected_id: Optional[str] = None) -> Optional[str]:
        screens = self.flow_data.screens
        if not screens: return None

        new_signature = self.extract_text_from_image(frame_bgr)

        if expected_id and expected_id in screens:
            info = screens[expected_id]
            expected_name = info.name
            logger.debug(f"Prioritizing match for expected screen: {expected_id} ('{expected_name}')")
            if info.signature and new_signature and (1 - self.jaccard_similarity(info.signature, new_signature)) < 0.2:
                 logger.debug(f"Signature match for expected screen {expected_id}")
                 return expected_id

            for path in info.paths:
                if not Path(path).exists(): continue
                img = cv2.imread(path)
                if img is None: continue

                gray_ref = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if (gray_new := self._frame_to_gray(frame_bgr, gray_ref.shape[::-1])) is None: continue

                score = self._ssim_match(gray_ref, gray_new)
                logger.debug(f"  - Comparing with expected screen ref {Path(path).name}: SSIM = {score:.4f}")
                if score > (SIMILARITY_THRESHOLD - 0.05):
                    logger.info(f"Confirmed expected screen {expected_id} with high confidence: {score:.4f}")
                    return expected_id

        logger.debug("Falling back to general screen match...")
        best_match_id = None
        highest_ssim = 0.0

        for screen_id, info in screens.items():
            if screen_id == expected_id: continue
            
            if info.signature and new_signature and (1 - self.jaccard_similarity(info.signature, new_signature)) > 0.3:
                continue

            for path in info.paths:
                if not Path(path).exists():
                    logger.warning(f"Image path not found: {path}")
                    continue

                img = cv2.imread(path)
                if img is None:
                    logger.warning(f"Failed to read image: {path}")
                    continue

                gray_ref = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                if (gray_new := self._frame_to_gray(frame_bgr, gray_ref.shape[::-1])) is None: continue

                score = self._ssim_match(gray_ref, gray_new)
                logger.debug(f"  - Comparing with {Path(path).name}: SSIM = {score:.4f}")

                if score > highest_ssim:
                    highest_ssim = score
                    best_match_id = screen_id

        if highest_ssim > SIMILARITY_THRESHOLD:
            screen = self.flow_data.screens.get(best_match_id)
            name = screen.name if screen else "?"
            logger.info(f"Found best match: screen {best_match_id} ('{name}') with SSIM {highest_ssim:.4f}")
            return best_match_id

        logger.warning(f"No suitable match found. Highest SSIM: {highest_ssim:.4f} (Threshold: {SIMILARITY_THRESHOLD})")
        return None

    def jaccard_similarity(self, str1, str2):
        set1 = set(str1.split())
        set2 = set(str2.split())
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union != 0 else 0

    def capture_and_identify_screen(self, auto_name=False, frame=None) -> Tuple[Optional[str], bool]:
        new_img = frame if frame is not None else adb_utils.adb_capture(self.serial)
        if new_img is None: logger.error("Failed to capture screen."); return None, False

        if (matched_id := self.match_existing_screen(new_img)):
            logger.info(f"Matched existing: {matched_id}")
            screen_name = self.flow_data.screens[matched_id].name
            new_path = IMAGES_DIR / f"{matched_id}_{screen_name}_{adb_utils.now_tag()}.png"
            cv2.imwrite(str(new_path), new_img)
            self._append_ref_image(matched_id, str(new_path))
            logger.info(f"Added new ref image to existing screen {matched_id}")
            return matched_id, False

        new_signature = self.extract_text_from_image(new_img)

        if auto_name:
            screen_name = f"Screen_{len(self.flow_data.screens) + 1}"
        else:
            screen_name = self.ask_screen_name()
        
        if not screen_name: return None, False

        screens = self.flow_data.screens
        if (same_name_ids := [sid for sid, info in screens.items() if info.name == screen_name]):
            canonical_id = self.merge_screens_by_name_keep_images(screen_name, prefer_id=min(same_name_ids, key=lambda s: int(s)))
            new_path = IMAGES_DIR / f"{canonical_id}_{screen_name}_{adb_utils.now_tag()}.png"
            cv2.imwrite(str(new_path), new_img)
            self._append_ref_image(canonical_id, str(new_path))
            logger.info(f"Added new ref image to screen {canonical_id}: {new_path.name}")
            return canonical_id, True

        new_id = str(max(map(int, screens.keys())) + 1 if screens else 1)
        new_path = IMAGES_DIR / f"{new_id}_{screen_name}_{adb_utils.now_tag()}.png"
        cv2.imwrite(str(new_path), new_img)
        self.flow_data.screens[new_id] = Screen(id=new_id, name=screen_name, paths=[str(new_path)], signature=new_signature)
        self.session_stats.screens_found += 1
        save_flow_data(self.flow_data)
        logger.info(f"Saved NEW screen: {screen_name} (ID: {new_id}, refs=1)")
        return new_id, True

    def check_and_add_transition(self, from_id: str, to_id: str, events: List[TouchEvent]):
        sorted_events = sorted(events, key=lambda e: e.time)

        for t in self.flow_data.transitions:
            if t.from_id == from_id and t.to_id == to_id:
                t.touch_events = sorted_events
                save_flow_data(self.flow_data)
                logger.info(f"Updated events for existing transition: {from_id} -> {to_id}"); return

        self.flow_data.transitions.append(Transition(from_id=from_id, to_id=to_id, touch_events=sorted_events))
        self.session_stats.transitions_found += 1
        save_flow_data(self.flow_data)
        logger.info(f"Added new transition with events: {from_id} -> {to_id}")

    @pyqtSlot(str, int)
    def set_status(self, message: str, duration: int = 5000):
        self.status_message = message
        self.update()
        if duration > 0:
            QTimer.singleShot(duration, self.clear_status)

    @pyqtSlot()
    def clear_status(self):
        self.status_message = ""
        self.update()

    @pyqtSlot(result=str)
    def ask_screen_name_from_main_thread(self) -> Optional[str]:
        return self.ask_screen_name()

    def ask_screen_name(self) -> Optional[str]:
        if threading.current_thread() != threading.main_thread():
            return QMetaObject.invokeMethod(self, "ask_screen_name_from_main_thread", Qt.BlockingQueuedConnection)

        text, ok = QInputDialog.getText(self, "New Screen", "Enter screen name:", QLineEdit.Normal, "")
        return text if ok and text else None

    def show_diagram(self):
        if not self.flow_data.screens: self.set_status("No data for diagram."); return
        self.diagram_widget = DiagramWidget(self, self.flow_data, self.serial, on_save=lambda: save_flow_data(self.flow_data))
        self.diagram_widget.show()
        if (frame := adb_utils.adb_capture(self.serial)) is not None and (sid := self.match_existing_screen(frame)):
            self.diagram_widget.set_current_screen_id(sid, center=True)

    def replay_thread(self, events, on_finish):
        normalized = [e if isinstance(e, dict) else e.__dict__ for e in events]
        threading.Thread(target=replay_touch_events, args=(self.serial, normalized, on_finish), daemon=True).start()

    def _cap_ref_images(self, paths: List[str]) -> List[str]:
        ordered = sorted(paths, key=lambda p: Path(p).stat().st_mtime if Path(p).exists() else 0)
        if len(ordered) <= MAX_REF_IMAGES: return ordered
        to_remove = ordered[:-MAX_REF_IMAGES]
        for rp in to_remove: Path(rp).unlink(missing_ok=True)
        return ordered[-MAX_REF_IMAGES:]

    def _append_ref_image(self, screen_id: str, new_path: str):
        screen = self.flow_data.screens.get(screen_id)
        if not screen: return
        if new_path not in screen.paths: screen.paths.append(str(new_path))
        screen.paths = self._cap_ref_images(screen.paths)
        save_flow_data(self.flow_data)

    def merge_screens_by_name_keep_images(self, screen_name: str, prefer_id: Optional[str] = None) -> Optional[str]:
        screens = self.flow_data.screens
        same_name_ids = [sid for sid, info in screens.items() if info.name == screen_name]
        if len(same_name_ids) <= 1: return same_name_ids[0] if same_name_ids else None

        canonical_id = prefer_id if prefer_id and prefer_id in same_name_ids else min(same_name_ids, key=lambda s: int(s))
        canonical_screen = screens[canonical_id]

        if not canonical_screen.pos:
            for sid in same_name_ids:
                if sid != canonical_id and (screen := screens.get(sid)) and isinstance(screen.pos, (list, tuple)) and len(screen.pos) == 2:
                    canonical_screen.pos = screen.pos; break

        merged_paths: List[str] = list(canonical_screen.paths)
        for sid in same_name_ids:
            if sid == canonical_id: continue
            if screen_to_merge := screens.get(sid):
                for p in screen_to_merge.paths:
                    if p not in merged_paths: merged_paths.append(p)
                for t in self.flow_data.transitions:
                    if t.from_id == sid: t.from_id = canonical_id
                    if t.to_id == sid: t.to_id = canonical_id
                del screens[sid]

        canonical_screen.paths = self._cap_ref_images(merged_paths)
        save_flow_data(self.flow_data)
        logger.info(f"[MERGE/CAP] name='{screen_name}' -> ID={canonical_id}, refs={len(canonical_screen.paths)}")
        return canonical_id

    def toggle_exploration(self):
        if not self.detector:
            self.set_status("UI Detector not available. Cannot explore.", 5000)
            return
        if not self.ocr_reader:
            self.set_status("OCR reader not available. Exploration may be less accurate.", 5000)

        if self.is_exploring:
            self.is_exploring = False
            self.exploration_stop_event.set()
            if self.exploration_thread and self.exploration_thread.is_alive():
                self.exploration_thread.join(timeout=5.0)
            self.set_status("Exploration stopped.", 3000)
        else:
            self.is_exploring = True
            self.exploration_stop_event.clear()
            self.exploration_thread = threading.Thread(target=self._exploration_loop, daemon=True)
            self.exploration_thread.start()
            self.set_status("Exploration started...", 3000)

    def wait_for_screen_stable(self, timeout=7, interval=0.3) -> Optional[np.ndarray]:
        start_time = time.time()
        last_frame = adb_utils.adb_capture(self.serial)
        if last_frame is None: return None

        while time.time() - start_time < timeout:
            if self.exploration_stop_event.is_set(): return None
            time.sleep(interval)
            current_frame = adb_utils.adb_capture(self.serial)
            if current_frame is None: continue

            last_gray = self._frame_to_gray(last_frame, (32, 32))
            current_gray = self._frame_to_gray(current_frame, (32, 32))

            if last_gray is not None and current_gray is not None:
                score = self._ssim_match(last_gray, current_gray)
                if score > 0.99:
                    logger.info(f"Screen stabilized with SSIM score: {score:.4f}")
                    return current_frame
            
            last_frame = current_frame
        
        logger.warning(f"Screen did not stabilize within {timeout} seconds.")
        return last_frame

    def _exploration_loop(self):
        visited_screens = set()
        q = deque()
        start_time = time.time()

        current_frame = self.wait_for_screen_stable()
        if current_frame is None: self.is_exploring = False; return

        root_screen_id, is_new = self.capture_and_identify_screen(auto_name=True, frame=current_frame)
        if not root_screen_id:
            self.is_exploring = False
            return
        
        q.append((root_screen_id, 0)) # (screen_id, depth)
        visited_screens.add(root_screen_id)

        while self.is_exploring and q:
            if (time.time() - start_time) > MAX_EXPLORATION_TIME_SEC:
                logger.info(f"Exploration time limit ({MAX_EXPLORATION_TIME_SEC}s) reached.")
                break

            from_screen_id, depth = q.popleft()
            if depth >= MAX_EXPLORATION_DEPTH:
                logger.info(f"Max exploration depth ({MAX_EXPLORATION_DEPTH}) reached at screen {from_screen_id}.")
                continue

            logger.info(f"Exploring from screen: {from_screen_id} at depth {depth}")

            current_frame = adb_utils.adb_capture(self.serial)
            if current_frame is None: continue
            clickable_elements = self.detector.detect_clickable_elements(current_frame)

            if not clickable_elements:
                if from_screen_id == root_screen_id:
                    logger.info("No clickable elements on root screen. Stopping exploration.")
                    break
                self.u2_device.press("back")
                new_frame = self.wait_for_screen_stable()
                if new_frame is None: continue
                new_screen_id, _ = self.capture_and_identify_screen(auto_name=True, frame=new_frame)
                if new_screen_id and new_screen_id not in visited_screens:
                    q.append((new_screen_id, depth))
                    visited_screens.add(new_screen_id)
                continue

            # Separate back buttons from general clickable elements
            back_buttons = []
            general_buttons = []
            for bounds, text in clickable_elements:
                if self._contains_any_keyword(text, BACK_BUTTON_KEYWORDS):
                    back_buttons.append((bounds, text))
                elif not self._contains_any_keyword(text, SENSITIVE_KEYWORDS):
                    general_buttons.append((bounds, text))
                else:
                    logger.info(f"Skipping sensitive element with text: '{text}'")

            # Explore general buttons first
            for bounds, text in general_buttons:
                if self.exploration_stop_event.is_set(): break

                x1, y1, x2, y2 = bounds
                tap_x, tap_y = (x1 + x2) // 2, (y1 + y2) // 2
                
                u, v = self.transform.to_natural_normalized(tap_x, tap_y)
                touch_event = TouchEvent(type="tap", u=round(u, 4), v=round(v, 4), time=0.0)

                logger.info(f"Tapping element at ({tap_x}, {tap_y}) with text: '{text}'")
                adb_utils.adb_tap(self.serial, tap_x, tap_y)
                
                to_frame = self.wait_for_screen_stable()
                if to_frame is None: continue

                to_screen_id, is_new = self.capture_and_identify_screen(auto_name=True, frame=to_frame)
                if not to_screen_id: continue

                existing_transition = next((t for t in self.flow_data.transitions if t.from_id == from_screen_id and t.to_id == to_screen_id), None)
                if not existing_transition:
                    self.check_and_add_transition(from_screen_id, to_screen_id, [touch_event])

                if to_screen_id not in visited_screens:
                    visited_screens.add(to_screen_id)
                    q.append((to_screen_id, depth + 1))
                    logger.info(f"New screen found: {to_screen_id}")
                
                # After exploring a path, go back to the previous screen
                if back_buttons:
                    (x1_b, y1_b, x2_b, y2_b), back_text = back_buttons[0]
                    tap_x_b, tap_y_b = (x1_b + x2_b) // 2, (y1_b + y2_b) // 2
                    logger.info(f"Tapping back button at ({tap_x_b}, {tap_y_b}) with text: '{back_text}'")
                    adb_utils.adb_tap(self.serial, tap_x_b, tap_y_b)
                else:
                    self.u2_device.press("back")
                
                back_frame = self.wait_for_screen_stable()
                if back_frame is None: break

                current_screen_after_back, _ = self.capture_and_identify_screen(auto_name=True, frame=back_frame)
                if current_screen_after_back != from_screen_id:
                    logger.warning("Failed to return to the previous screen. Re-evaluating current screen.")
                    if current_screen_after_back and current_screen_after_back not in visited_screens:
                        q.append((current_screen_after_back, depth))
                        visited_screens.add(current_screen_after_back)
                    break

        self.is_exploring = False
        logger.info("Exploration finished.")
        QMetaObject.invokeMethod(self, "set_status", Qt.QueuedConnection, Q_ARG(str, "Exploration finished."), Q_ARG(int, 5000))

    def _contains_any_keyword(self, text: str, keyword_dict: Dict[str, tuple]) -> bool:
        if not text:
            return False
        t = text.lower()
        for lang, words in keyword_dict.items():
            for w in words:
                if not w:
                    continue
                if w.lower() in t:
                    return True
        return False
