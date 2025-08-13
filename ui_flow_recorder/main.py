import sys, os, argparse, time, subprocess, threading, json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np
import cv2
from skimage.metrics import structural_similarity as ssim
import math
from PyQt5.QtCore import Qt, QPoint, QRect, QPointF
from PyQt5.QtGui import QPainter, QColor, QPen, QGuiApplication, QPolygonF, QCursor, QVector2D
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QMenu, QAction, QMessageBox

# --- Constants ---
DATA_FILE = Path(__file__).parent / "flow_data.json"
IMAGES_DIR = Path(__file__).parent / "images"
SIMILARITY_THRESHOLD = 0.90
MAX_REF_IMAGES = 10  # 화면별 참조 이미지 최대 보유 개수

# --- Helper Functions ---
def get_device_serials(max_devices: int = 1) -> List[str]:
    lines = subprocess.check_output(["adb", "devices"]).decode().strip().splitlines()[1:]
    return [l.split()[0] for l in lines if l.strip().endswith("device")][:max_devices]

def get_device_resolution(serial: str) -> Tuple[int, int]:
    output = subprocess.check_output(["adb", "-s", serial, "shell", "wm", "size"]).decode()
    w, h = map(int, output.strip().split(": ")[-1].split("x"))
    if h > w:
        w, h = h, w
    return w, h

def adb_tap(serial: str, x: int, y: int):
    subprocess.run(["adb", "-s", serial, "shell", "input", "tap", str(x), str(y)])

def adb_swipe(serial: str, x1: int, y1: int, x2: int, y2: int, duration: int):
    subprocess.run(["adb", "-s", serial, "shell", "input", "swipe", 
                    str(x1), str(y1), str(x2), str(y2), str(duration)])

def adb_capture(serial: str) -> Optional[np.ndarray]:
    proc = subprocess.run(
        ["adb", "-s", serial, "exec-out", "screencap", "-p"],
        capture_output=True, check=True
    )
    if proc.returncode == 0:
        image_data = np.frombuffer(proc.stdout, np.uint8)
        if image_data.tobytes().startswith(b'\r\n'):
            image_data = image_data[2:]
        return cv2.imdecode(image_data, cv2.IMREAD_COLOR)
    return None

def ensure_images_dir():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def replay_touch_events(serial: str, events: List[Dict], on_finish=None):
    """Replays a list of touch events via ADB."""
    try:
        start_time = time.perf_counter()
        for event in sorted(events, key=lambda e: e['time']):
            event_time = event['time']
            delay = (start_time + event_time) - time.perf_counter()
            if delay > 0:
                time.sleep(delay)

            if event['type'] == 'tap':
                print(f"Replaying tap: {event}")
                adb_tap(serial, event['x'], event['y'])
            elif event['type'] == 'swipe':
                print(f"Replaying swipe: {event}")
                adb_swipe(serial, event['x1'], event['y1'], event['x2'], event['y2'], event['duration'])
    finally:
        if callable(on_finish):
            on_finish()

# --- Main Application Class ---
class FlowRecorder(QWidget):
    def __init__(self, serial: str, win_name: str = "UI Flow Recorder"):
        super().__init__()
        self.serial = serial
        self.device_w, self.device_h = get_device_resolution(serial)

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

        self.adb_executing = False
        self.status_message = ""
        self.diagram_widget = None

        ensure_images_dir()
        self.load_flow_data()

    def _normalize_schema(self):
        screens: Dict[str, Any] = self.flow_data.setdefault('screens', {})
        for sid, info in list(screens.items()):
            if 'paths' not in info:
                p = info.get('path')
                info['paths'] = [p] if isinstance(p, str) and p else []
                info.pop('path', None)

    def load_flow_data(self):
        if DATA_FILE.exists() and DATA_FILE.stat().st_size > 0:
            with open(DATA_FILE, "r") as f:
                self.flow_data = json.load(f)
        else:
            self.flow_data = {}
        self.flow_data.setdefault('screens', {})
        self.flow_data.setdefault('transitions', [])
        self._normalize_schema()

    def save_flow_data(self):
        self._normalize_schema()
        with open(DATA_FILE, "w") as f: json.dump(self.flow_data, f, indent=4)

    def _cap_ref_images(self, paths: List[str]) -> List[str]:
        ordered = sorted(paths, key=lambda p: Path(p).stat().st_mtime if Path(p).exists() else 0)
        if len(ordered) <= MAX_REF_IMAGES: return ordered
        to_remove = ordered[:-MAX_REF_IMAGES]
        for rp in to_remove: Path(rp).unlink(missing_ok=True)
        return ordered[-MAX_REF_IMAGES:]

    def _append_ref_image(self, screen_id: str, new_path: str):
        screens = self.flow_data['screens']
        info = screens.setdefault(screen_id, {})
        info.setdefault('paths', [])
        if new_path not in info['paths']: info['paths'].append(str(new_path))
        info['paths'] = self._cap_ref_images(info['paths'])
        self.save_flow_data()

    def _dedup_transitions(self):
        seen, deduped = set(), []
        for t in self.flow_data.get('transitions', []):
            key = (t.get('from'), t.get('to'))
            if key not in seen: seen.add(key); deduped.append(t)
        self.flow_data['transitions'] = deduped

    def merge_screens_by_name_keep_images(self, screen_name: str, prefer_id: Optional[str] = None) -> Optional[str]:
        screens = self.flow_data.get('screens', {})
        same_name_ids = [sid for sid, info in screens.items() if info.get('name') == screen_name]
        if len(same_name_ids) <= 1: return same_name_ids[0] if same_name_ids else None

        canonical_id = prefer_id if prefer_id and prefer_id in same_name_ids else min(same_name_ids, key=lambda s: int(s))

        if not screens[canonical_id].get('pos'):
            for sid in same_name_ids:
                if sid != canonical_id and (pos := screens[sid].get('pos')) and isinstance(pos, (list, tuple)) and len(pos) == 2: screens[canonical_id]['pos'] = [int(pos[0]), int(pos[1])]; break

        merged_paths: List[str] = list(screens[canonical_id].get('paths', []))
        for sid in same_name_ids:
            if sid == canonical_id: continue
            for p in screens[sid].get('paths', []): 
                if p not in merged_paths: merged_paths.append(p)
            for t in self.flow_data.get('transitions', []):
                if t.get('from') == sid: t['from'] = canonical_id
                if t.get('to') == sid: t['to'] = canonical_id
            del screens[sid]

        screens[canonical_id]['paths'] = self._cap_ref_images(merged_paths)
        self._dedup_transitions()
        self.save_flow_data()
        print(f"[MERGE/CAP] name='{screen_name}' -> ID={canonical_id}, refs={len(screens[canonical_id]['paths'])}")
        return canonical_id

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(255, 0, 0) if self.is_path_recording else QColor(0, 255, 0)); pen.setWidth(5)
        p.setPen(pen); p.drawRect(0, 0, self.viewer_w - 1, self.viewer_h - 1)
        p.setPen(QColor(255, 255, 255))
        p.drawText(20, 40, f"Device: {self.serial}")
        p.drawText(20, 60, "R: Start Path, C: End Path, G: Diagram, ESC: Quit")
        if self.is_path_recording:
            start_screen_name = self.flow_data['screens'].get(self.path_start_screen_id, {}).get('name', 'UNKNOWN')
            p.drawText(20, 80, f"[RECORDING] From: '{start_screen_name}'. Press 'C' to end.")
        if self.status_message: p.drawText(20, 100, self.status_message)
        if self.adb_executing: p.drawText(20, self.viewer_h - 20, "Executing ADB...")

    def keyPressEvent(self, e):
        key_map = {Qt.Key_Escape: QApplication.quit, Qt.Key_R: self.start_path_recording, 
                   Qt.Key_C: self.capture_and_end_path, Qt.Key_G: self.show_diagram}
        if (action := key_map.get(e.key())): action()
        else: super().keyPressEvent(e)

    def _map_to_device(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        scale = self.viewer_h / self.device_h
        eff_w = self.device_w * scale
        off_x = (self.viewer_w - eff_w) / 2
        if not (off_x <= x <= off_x + eff_w): return None
        return int((x - off_x) * self.device_w / eff_w), int(y * self.device_h / self.viewer_h)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.is_event_recording and (coords := self._map_to_device(e.pos().x(), e.pos().y())):
            self.drag_start_pos = coords
            self.drag_start_time = time.perf_counter()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not (px_py := self._map_to_device(e.pos().x(), e.pos().y())): return
        px, py = px_py
        if self.is_event_recording and self.drag_start_pos:
            sx, sy = self.drag_start_pos
            duration_ms = int((time.perf_counter() - self.drag_start_time) * 1000)
            event_time = time.perf_counter() - self.path_start_time
            if abs(px - sx) < 5 and abs(py - sy) < 5:
                event = {"type": "tap", "x": px, "y": py, 'time': round(event_time, 4)}
                adb_tap(self.serial, px, py)
            else:
                event = {"type": "swipe", "x1": sx, "y1": sy, "x2": px, "y2": py, "duration": max(duration_ms, 50), 'time': round(event_time, 4)}
                adb_swipe(self.serial, sx, sy, px, py, max(duration_ms, 50))
            self.recorded_events.append(event)
            print(f"Event recorded: {event}")
            self.drag_start_pos = self.drag_start_time = None
        else: adb_tap(self.serial, px, py)

    def start_path_recording(self):
        if self.is_path_recording: self.set_status("Already recording. Press 'C' to complete."); return
        self.set_status("Capturing start screen..."); self.adb_executing = True; self.update(); QApplication.processEvents()
        screen_id, _ = self.capture_and_identify_screen()
        if screen_id:
            self.is_path_recording = self.is_event_recording = True
            self.path_start_screen_id = screen_id
            self.path_start_time = time.perf_counter()
            self.recorded_events = []
            start_screen_name = self.flow_data['screens'][screen_id]['name']
            self.set_status(f"Path started from '{start_screen_name}'. Navigate and press 'C'.")
        else: self.set_status("Failed to identify start screen.")
        self.adb_executing = False; self.update()

    def capture_and_end_path(self):
        if not self.is_path_recording: self.set_status("Not recording. Press 'R' to start."); return
        self.is_event_recording = False
        self.set_status("Capturing destination screen..."); self.adb_executing = True; self.update(); QApplication.processEvents()
        to_screen_id, _ = self.capture_and_identify_screen()
        if to_screen_id:
            from_screen_id = self.path_start_screen_id
            self.check_and_add_transition(from_screen_id, to_screen_id, self.recorded_events)
            to_screen_name = self.flow_data['screens'][to_screen_id]['name']
            self.set_status(f"Path recorded: {self.flow_data['screens'][from_screen_id]['name']} -> {to_screen_name}")
            if self.diagram_widget: self.diagram_widget.set_current_screen_id(to_screen_id, center=True)
        else: self.set_status("Failed to identify destination screen.")
        self.is_path_recording = self.path_start_screen_id = None
        self.adb_executing = False; self.update()

    def _ssim_match(self, ref_img_gray: np.ndarray, new_img_gray: np.ndarray) -> float:
        try: return float(ssim(ref_img_gray, new_img_gray, full=True)[0])
        except Exception: return 0.0

    def _frame_to_gray(self, frame_bgr: np.ndarray, size: Tuple[int, int]) -> Optional[np.ndarray]:
        try: return cv2.resize(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), size)
        except Exception: return None

    def match_existing_screen(self, frame_bgr: np.ndarray) -> Optional[str]:
        screens = self.flow_data.get("screens", {})
        if not screens: return None
        for screen_id, info in screens.items():
            for path in info.get("paths", []):
                if (img := cv2.imread(path)) is None: continue
                gray_ref = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if (gray_new := self._frame_to_gray(frame_bgr, gray_ref.shape[::-1])) is None: continue
                if self._ssim_match(gray_ref, gray_new) > SIMILARITY_THRESHOLD: return screen_id
        return None

    def capture_and_identify_screen(self) -> Tuple[Optional[str], bool]:
        if (new_img := adb_capture(self.serial)) is None: print("Failed to capture screen."); return None, False
        if (matched_id := self.match_existing_screen(new_img)): print(f"Matched existing: {matched_id}"); return matched_id, False
        if not (screen_name := self.ask_screen_name()): return None, False
        screens = self.flow_data["screens"]
        if (same_name_ids := [sid for sid, info in screens.items() if info.get("name") == screen_name]):
            canonical_id = self.merge_screens_by_name_keep_images(screen_name, prefer_id=min(same_name_ids, key=lambda s: int(s)))
            new_path = IMAGES_DIR / f"{canonical_id}_{screen_name}_{now_tag()}.png"
            cv2.imwrite(str(new_path), new_img)
            self._append_ref_image(canonical_id, str(new_path))
            print(f"Added new ref image to screen {canonical_id}: {new_path.name}")
            return canonical_id, False
        new_id = str(max(map(int, screens.keys())) + 1 if screens else 1)
        new_path = IMAGES_DIR / f"{new_id}_{screen_name}_{now_tag()}.png"
        cv2.imwrite(str(new_path), new_img)
        screens[new_id] = {"name": screen_name, "paths": [str(new_path)]}
        self.save_flow_data()
        print(f"Saved NEW screen: {screen_name} (ID: {new_id}, refs=1)")
        return new_id, True

    def check_and_add_transition(self, from_id: str, to_id: str, events: List[Dict]):
        for t in self.flow_data["transitions"]:
            if t["from"] == from_id and t["to"] == to_id:
                t["touch_events"] = events; self.save_flow_data()
                print(f"Added events to existing transition: {from_id} -> {to_id}"); return
        self.flow_data["transitions"].append({"from": from_id, "to": to_id, "coords": None, "touch_events": events})
        self.save_flow_data()
        print(f"Added new transition with events: {from_id} -> {to_id}")

    def set_status(self, message: str, duration: int = 5000):
        self.status_message = message; self.update()
        threading.Timer(duration / 1000, self.clear_status).start()

    def clear_status(self):
        self.status_message = ""; self.update()

    def ask_screen_name(self) -> Optional[str]:
        text, ok = QInputDialog.getText(self, "New Screen", "Enter screen name:", QLineEdit.Normal, "")
        return text if ok and text else None

    def show_diagram(self):
        if not self.flow_data.get("screens"): self.set_status("No data for diagram."); return
        self.diagram_widget = DiagramWidget(self, self.flow_data, self.serial, on_save=self.save_flow_data)
        self.diagram_widget.show()
        if (frame := adb_capture(self.serial)) is not None and (sid := self.match_existing_screen(frame)):
            self.diagram_widget.set_current_screen_id(sid, center=True)

# --- Diagram Widget ---
class DiagramWidget(QWidget):
    def __init__(self, main_window, flow_data, serial, on_save=None):
        super().__init__()
        self.main_window, self.flow_data, self.serial, self.on_save = main_window, flow_data, serial, on_save
        self.node_positions: Dict[str, QPoint] = {}
        self.node_rects: Dict[str, QRect] = {}
        self.dragged_node_id: Optional[str] = None
        self.scale, self.pan_x, self.pan_y = 1.0, 0.0, 0.0
        self.min_scale, self.max_scale = 0.25, 3.0
        self.is_panning = False; self.last_mouse_pos_device = QPoint()
        self.current_screen_id: Optional[str] = None
        self.setWindowTitle("UI Flow Diagram"); self.setStyleSheet("background-color: white;")
        self.setMinimumSize(800, 600); self.setMouseTracking(True)
        self.calculate_layout()

    def device_to_world(self, pt: QPoint) -> QPointF: return QPointF((pt.x() - self.pan_x) / self.scale, (pt.y() - self.pan_y) / self.scale)
    def world_to_device(self, pt: QPointF) -> QPointF: return QPointF(pt.x() * self.scale + self.pan_x, pt.y() * self.scale + self.pan_y)
    def rebuild_node_rects(self): self.node_rects = {sid: QRect(int(pos.x()), int(pos.y()), 150, 50) for sid, pos in self.node_positions.items()}

    def calculate_layout(self):
        screens = self.flow_data.get("screens", {})
        if not screens: return
        for sid, info in screens.items():
            if (pos := info.get("pos")) and isinstance(pos, list) and len(pos) == 2: self.node_positions[sid] = QPoint(*pos)
        missing = [sid for sid in screens if sid not in self.node_positions]
        if not missing: return
        levels = {sid: 0 for sid in screens}
        for t in self.flow_data.get("transitions", []): levels[t["to"]] = max(levels[t["to"]], levels[t["from"]] + 1)
        level_counts = {i: [sid for sid, l in levels.items() if l == i] for i in range(max(levels.values()) + 1)}
        for level, sids in level_counts.items():
            y = level * 150 + 100
            start_x = (self.width() - len(sids) * 200 + 50) / 2
            for i, sid in enumerate(sids):
                if sid in missing: self.node_positions[sid] = QPoint(int(start_x + i * 200), y)

    def paintEvent(self, event):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.pan_x, self.pan_y); p.scale(self.scale, self.scale)
        self.rebuild_node_rects()
        for t in self.flow_data.get("transitions", []):
            if (r1 := self.node_rects.get(t["from"])) and (r2 := self.node_rects.get(t["to"])):
                self.draw_arrow(p, r1, r2, bool(t.get("touch_events")))
        for sid, rect in self.node_rects.items():
            p.setBrush(QColor("#FFF3CD") if sid == self.current_screen_id else QColor("#e0e0e0"))
            p.setPen(QPen(QColor("#FF9800"), 3) if sid == self.current_screen_id else Qt.black)
            p.drawRoundedRect(rect, 10, 10)
            p.drawText(rect, Qt.AlignCenter, self.flow_data["screens"].get(sid, {}).get("name", sid))

    def _get_intersection_point(self, rect: QRect, target_point: QPoint) -> QPoint:
        center = rect.center(); dx, dy = target_point.x() - center.x(), target_point.y() - center.y()
        if dx == 0 and dy == 0: return center
        t = min(abs(rect.width() / (2 * dx)) if dx else float('inf'), abs(rect.height() / (2 * dy)) if dy else float('inf'))
        return QPoint(center.x() + int(dx * t), center.y() + int(dy * t))

    def draw_arrow(self, p, r1, r2, has_events):
        p1, p2 = self._get_intersection_point(r1, r2.center()), self._get_intersection_point(r2, r1.center())
        pen_color = QColor("#0078D7") if has_events else Qt.black
        pen_width = 3 if has_events else 2
        p.setPen(QPen(pen_color, pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(p1, p2)
        angle = math.atan2(p1.y() - p2.y(), p1.x() - p2.x())
        arrow_p1 = p2 + QPoint(int(math.cos(angle + math.pi / 6) * 15), int(math.sin(angle + math.pi / 6) * 15))
        arrow_p2 = p2 + QPoint(int(math.cos(angle - math.pi / 6) * 15), int(math.sin(angle - math.pi / 6) * 15))
        p.setBrush(pen_color); p.drawPolygon(QPolygonF([p2, arrow_p1, arrow_p2]))

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0: return
        zoom_factor = 1.15 if delta > 0 else 1 / 1.15
        old_scale, self.scale = self.scale, max(self.min_scale, min(self.max_scale, self.scale * zoom_factor))
        if abs(self.scale - old_scale) < 1e-6: return
        world_before = self.device_to_world(event.pos())
        self.pan_x = event.pos().x() - world_before.x() * self.scale
        self.pan_y = event.pos().y() - world_before.y() * self.scale
        self.update(); event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            world_pt = self.device_to_world(event.pos())
            if (sid := self.get_node_at(event.pos())):
                self.dragged_node_id = sid
                self.drag_offset_world = world_pt - QPointF(self.node_rects[sid].topLeft())
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.is_panning = True; self.last_mouse_pos_device = event.pos(); self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.dragged_node_id:
            new_top_left = self.device_to_world(event.pos()) - self.drag_offset_world
            self.node_positions[self.dragged_node_id] = new_top_left.toPoint()
        elif self.is_panning:
            delta = event.pos() - self.last_mouse_pos_device
            self.pan_x += delta.x(); self.pan_y += delta.y()
            self.last_mouse_pos_device = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.dragged_node_id and callable(self.on_save):
                pos = self.node_positions[self.dragged_node_id]
                self.flow_data["screens"][self.dragged_node_id]["pos"] = [pos.x(), pos.y()]
                self.on_save()
            self.dragged_node_id = None; self.is_panning = False; self.unsetCursor()

    def set_current_screen_id(self, sid: str, center: bool = False):
        if not sid: return
        self.current_screen_id = sid
        if center and sid in self.node_positions:
            self.rebuild_node_rects()
            if sid in self.node_rects:
                world_c = QPointF(self.node_rects[sid].center())
                self.pan_x = self.width() / 2.0 - world_c.x() * self.scale
                self.pan_y = self.height() / 2.0 - world_c.y() * self.scale
        self.update()

    def get_node_at(self, pos: QPoint) -> Optional[str]:
        world_pt = self.device_to_world(pos)
        for sid, rect in self.node_rects.items():
            if rect.contains(world_pt.toPoint()): return sid
        return None

    def get_transition_at(self, pos: QPoint) -> Optional[Dict]:
        world_pt = self.device_to_world(pos)
        for t in self.flow_data.get("transitions", []):
            if not (r1 := self.node_rects.get(t["from"])) or not (r2 := self.node_rects.get(t["to"])) : continue
            p1, p2 = QPointF(r1.center()), QPointF(r2.center())
            line_vec = QVector2D(p2 - p1)
            if line_vec.isNull(): continue

            world_pt_vec = QVector2D(world_pt - p1)
            dist = QVector2D.dotProduct(world_pt_vec, line_vec.normalized())

            if not (0 < dist < line_vec.length()): continue

            proj_point = p1 + (line_vec.normalized() * dist).toPointF()

            if QVector2D(world_pt - proj_point).length() < 10 / self.scale:
                return t
        return None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""            QMenu {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
            }
            QMenu::item:selected {
                background-color: #e8e8e8;
                color: black;
            }
            QMenu::item:disabled {
                color: #a0a0a0;
            }
        """)
        if (clicked_transition := self.get_transition_at(event.pos())) and (events := clicked_transition.get("touch_events")):
            action = QAction("Replay Path", self)
            action.triggered.connect(lambda: self.replay_path(events, final_node_id=clicked_transition.get('to')))
            menu.addAction(action)
        elif clicked_node_id := self.get_node_at(event.pos()):
            if self.current_screen_id and self.current_screen_id != clicked_node_id:
                start_name = self.flow_data['screens'].get(self.current_screen_id, {}).get('name', 'Unknown')
                replay_action = QAction(f"Replay path from '{start_name}'", self)
                replay_action.triggered.connect(lambda: self.replay_path_to_node(clicked_node_id))
                menu.addAction(replay_action)
                menu.addSeparator()
            
            add_action = QAction("Add Connection", self); add_action.triggered.connect(lambda: self.add_connection(clicked_node_id)); menu.addAction(add_action)
            delete_menu = menu.addMenu("Delete Connection")
            connected = [t for t in self.flow_data.get('transitions', []) if t.get('from') == clicked_node_id or t.get('to') == clicked_node_id]
            if not connected: delete_menu.setEnabled(False)
            else:
                for t in connected:
                    from_id, to_id = t.get('from'), t.get('to')
                    from_name = self.flow_data['screens'].get(from_id, {}).get('name', 'Unknown')
                    to_name = self.flow_data['screens'].get(to_id, {}).get('name', 'Unknown')
                    del_action = QAction(f"{from_name} → {to_name}", self)
                    del_action.triggered.connect(lambda c, f=from_id, to=to_id: self.delete_connection(f, to));
                    delete_menu.addAction(del_action)
        else: return
        menu.exec_(event.globalPos())

    def replay_path(self, events: List[Dict], final_node_id: Optional[str] = None):
        def on_replay_finished():
            QMetaObject.invokeMethod(self, "verify_arrival", Qt.QueuedConnection, Q_ARG(str, final_node_id))

        print(f"Starting replay of {len(events)} events on thread...")
        threading.Thread(target=replay_touch_events, args=(self.serial, events, on_replay_finished), daemon=True).start()

    def verify_arrival(self, expected_node_id: str):
        if not expected_node_id: return

        print(f"Verifying arrival at screen ID: {expected_node_id}...")
        if (frame := adb_capture(self.serial)) is None:
            print("Failed to capture screen for verification.")
            return

        actual_node_id = self.main_window.match_existing_screen(frame)
        expected_name = self.flow_data['screens'].get(expected_node_id, {}).get('name', 'Unknown')

        if actual_node_id == expected_node_id:
            print(f"Successfully arrived at '{expected_name}'.")
            self.set_current_screen_id(actual_node_id, center=False)
        else:
            actual_name = self.flow_data['screens'].get(actual_node_id, {}).get('name', 'Unknown') if actual_node_id else "Unknown Screen"
            print(f"Arrival verification failed. Expected '{expected_name}', but arrived at '{actual_name}'.")
            msg_box = QMessageBox(self); msg_box.setStyleSheet("QLabel{ color: black; }"); msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"Expected to arrive at '{expected_name}' but ended up at '{actual_name}'.")
            msg_box.setWindowTitle("Verification Failed"); msg_box.exec_()

    def find_all_paths(self, start_id: str, end_id: str) -> List[List[str]]:
        adj = {}
        for t in self.flow_data.get('transitions', []):
            from_id, to_id = t.get('from'), t.get('to')
            if not from_id or not to_id: continue
            if from_id not in adj: adj[from_id] = []
            adj[from_id].append(to_id)

        paths = []
        def dfs_recursive(current_id, path, visited):
            if current_id == end_id:
                paths.append(path)
                return

            for neighbor_id in adj.get(current_id, []):
                if neighbor_id not in visited:
                    dfs_recursive(neighbor_id, path + [neighbor_id], visited | {neighbor_id})

        dfs_recursive(start_id, [start_id], {start_id})
        return paths

    def replay_path_to_node(self, target_node_id: str):
        start_node_id = self.current_screen_id
        if not start_node_id:
            msg_box = QMessageBox(self); msg_box.setStyleSheet("QLabel{ color: black; }"); msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("Current screen is unknown."); msg_box.setWindowTitle("Replay Warning"); msg_box.exec_()
            return

        all_possible_paths = self.find_all_paths(start_node_id, target_node_id)
        valid_paths_with_cost = []

        for path in all_possible_paths:
            is_valid = True
            total_cost = 0.0
            events_by_segment = []
            
            for i in range(len(path) - 1):
                from_id, to_id = path[i], path[i+1]
                transition = next((t for t in self.flow_data['transitions'] if t.get('from') == from_id and t.get('to') == to_id), None)
                
                if not transition or not (events := transition.get('touch_events')):
                    is_valid = False
                    break
                
                segment_duration = max((e['time'] for e in events), default=0)
                total_cost += segment_duration
                events_by_segment.append(events)

            if is_valid:
                valid_paths_with_cost.append({"path": path, "cost": total_cost, "events_by_segment": events_by_segment})

        if not valid_paths_with_cost:
            msg_box = QMessageBox(self); msg_box.setStyleSheet("QLabel{ color: black; }"); msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"No valid replayable path found to '{self.flow_data['screens'].get(target_node_id, {}).get('name', 'Unknown')}'.")
            msg_box.setWindowTitle("Replay Warning"); msg_box.exec_()
            return

        best_path_info = min(valid_paths_with_cost, key=lambda p: p['cost'])
        
        final_event_list = []
        time_offset = 0.0
        for segment_events in best_path_info['events_by_segment']:
            segment_duration = 0.0
            for event in sorted(segment_events, key=lambda e: e['time']):
                adjusted_event = event.copy()
                adjusted_event['time'] = round(event['time'] + time_offset, 4)
                final_event_list.append(adjusted_event)
                segment_duration = max(segment_duration, event['time'])
            time_offset += segment_duration + 1.0

        path_names = ' -> '.join(self.flow_data['screens'].get(sid, {}).get('name', sid) for sid in best_path_info['path'])
        print(f"Replaying lowest-cost path (Cost: {best_path_info['cost']:.2f}s): {path_names}")
        self.replay_path(final_event_list, final_node_id=best_path_info['path'][-1])

    def add_connection(self, from_id: str):
        screens = self.flow_data.get("screens", {})
        items = [f"{info.get('name', 'Unknown')} ({sid})" for sid, info in screens.items() if sid != from_id]
        if not items: return
        item, ok = QInputDialog.getItem(self, "Add Connection", "Select destination:", items, 0, False)
        if ok and item:
            to_id = item.split('(')[-1].strip(')')
            if any(t['from'] == from_id and t['to'] == to_id for t in self.flow_data.get('transitions', [])): return
            self.flow_data.setdefault('transitions', []).append({'from': from_id, 'to': to_id, 'coords': None})
            if callable(self.on_save): self.on_save()
            self.update()

    def delete_connection(self, from_id: str, to_id: str):
        transitions = self.flow_data.get('transitions', [])
        if (t_to_del := next((t for t in transitions if t.get('from') == from_id and t.get('to') == to_id), None)):
            transitions.remove(t_to_del)
            if callable(self.on_save): self.on_save()
            self.update()
            print(f"Deleted transition: {from_id} -> {to_id}")

def main():
    parser = argparse.ArgumentParser(description="UI Flow Recorder using ADB and OpenCV.")
    parser.add_argument("--serial", help="The device serial to connect to.")
    args = parser.parse_args()
    serials = get_device_serials(2)
    if len(serials) < 2: print("Two ADB devices required."); sys.exit(1)
    device_serial = args.serial or serials[1]
    print(f"Using device: {device_serial}")
    app = QApplication(sys.argv)
    recorder = FlowRecorder(serial=device_serial)
    scrcpy_proc = subprocess.Popen([
        "scrcpy", "--serial", device_serial, "--no-control", "--no-audio",
        "--window-title", f"scrcpy - {device_serial}", "--window-x", "0", "--window-y", "0",
        "--window-width", str(recorder.viewer_w), "--window-height", str(recorder.viewer_h),
        "--window-borderless", "--max-size", "960"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    time.sleep(2)
    recorder.show()
    try: sys.exit(app.exec_())
    finally:
        print("Cleaning up...")
        scrcpy_proc.terminate(); scrcpy_proc.wait()
        recorder.save_flow_data()
        print("Flow data saved. Exiting.")

if __name__ == "__main__":
    main()

