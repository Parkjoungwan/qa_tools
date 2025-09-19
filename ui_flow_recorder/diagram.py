import math
import time
from typing import List, Optional, Dict

import cv2
from PyQt5.QtCore import Qt, QPoint, QRect, QPointF, QMetaObject, Q_ARG, pyqtSlot
from PyQt5.QtGui import QPainter, QColor, QPen, QPolygonF, QVector2D
from PyQt5.QtWidgets import QWidget, QMenu, QAction, QMessageBox, QInputDialog

import adb_utils
from models import Transition
from config import REPLAY_SEGMENT_GAP_SEC, VERIFY_ARRIVAL_TIMEOUT_SEC, VERIFY_ARRIVAL_INTERVAL_SEC

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
        screens = self.flow_data.screens
        if not screens: return
        for sid, info in screens.items():
            if info.pos and isinstance(info.pos, (list, tuple)) and len(info.pos) == 2: self.node_positions[sid] = QPoint(*info.pos)
        missing = [sid for sid in screens if sid not in self.node_positions]
        if not missing: return
        levels = {sid: 0 for sid in screens}
        for t in self.flow_data.transitions:
            if t.from_id in levels and t.to_id in levels:
                 levels[t.to_id] = max(levels[t.to_id], levels[t.from_id] + 1)
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
        for t in self.flow_data.transitions:
            if (r1 := self.node_rects.get(t.from_id)) and (r2 := self.node_rects.get(t.to_id)):
                has_events = bool(t.touch_events) and not t.legacy
                self.draw_arrow(p, r1, r2, has_events)
        for sid, rect in self.node_rects.items():
            screen = self.flow_data.screens.get(sid)
            name = screen.name if screen else "UNKNOWN"
            p.setBrush(QColor("#FFF3CD") if sid == self.current_screen_id else QColor("#e0e0e0"))
            p.setPen(QPen(QColor("#FF9800"), 3) if sid == self.current_screen_id else Qt.black)
            p.drawRoundedRect(rect, 10, 10)
            p.drawText(rect, Qt.AlignCenter, name)

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
                if screen := self.flow_data.screens.get(self.dragged_node_id):
                    screen.pos = (pos.x(), pos.y())
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

    def get_transition_at(self, pos: QPoint) -> Optional[Transition]:
        world_pt = self.device_to_world(pos)
        for t in self.flow_data.transitions:
            if not (r1 := self.node_rects.get(t.from_id)) or not (r2 := self.node_rects.get(t.to_id)) : continue
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
        menu.setStyleSheet('''            QMenu {
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
        ''')
        if (clicked_transition := self.get_transition_at(event.pos())) and (events := clicked_transition.touch_events):
            action = QAction("Replay Path", self)
            if clicked_transition.legacy: 
                action.setEnabled(False)
                action.setText("Replay Path (Legacy - Not Replayable)")
            else:
                action.triggered.connect(lambda: self.replay_path(events, final_node_id=clicked_transition.to_id))
            menu.addAction(action)
        elif clicked_node_id := self.get_node_at(event.pos()):
            if self.current_screen_id and self.current_screen_id != clicked_node_id:
                start_screen = self.flow_data.screens.get(self.current_screen_id)
                start_name = start_screen.name if start_screen else "Unknown"
                replay_action = QAction(f"Replay path from '{start_name}'", self)
                replay_action.triggered.connect(lambda: self.replay_path_to_node(clicked_node_id))
                menu.addAction(replay_action)
                menu.addSeparator()

            add_action = QAction("Add Connection", self); add_action.triggered.connect(lambda: self.add_connection(clicked_node_id)); menu.addAction(add_action)
            delete_menu = menu.addMenu("Delete Connection")
            connected = [t for t in self.flow_data.transitions if t.from_id == clicked_node_id or t.to_id == clicked_node_id]
            if not connected: delete_menu.setEnabled(False)
            else:
                for t in connected:
                    from_id, to_id = t.from_id, t.to_id
                    from_screen = self.flow_data.screens.get(from_id)
                    to_screen = self.flow_data.screens.get(to_id)
                    from_name = from_screen.name if from_screen else "Unknown"
                    to_name = to_screen.name if to_screen else "Unknown"
                    del_action = QAction(f"{from_name} → {to_name}", self)
                    del_action.triggered.connect(lambda c, f=from_id, to=to_id: self.delete_connection(f, to));
                    delete_menu.addAction(del_action)
        else: return
        menu.exec_(event.globalPos())

    def replay_path(self, events: List, final_node_id: Optional[str] = None):
        def on_replay_finished():
            QMetaObject.invokeMethod(self, "verify_arrival", Qt.QueuedConnection, Q_ARG(str, final_node_id))

        print(f"Starting replay of {len(events)} events on thread...")
        self.main_window.replay_thread(events, on_replay_finished)

    @pyqtSlot(str)
    def verify_arrival(self, expected_node_id: str):
        if not expected_node_id: return

        logger.info(f"Verifying arrival at screen ID: {expected_node_id}...")
        start_time = time.time()
        
        while time.time() - start_time < VERIFY_ARRIVAL_TIMEOUT_SEC:
            frame = adb_utils.adb_capture(self.serial)
            if frame is None:
                time.sleep(VERIFY_ARRIVAL_INTERVAL_SEC)
                continue

            actual_node_id = self.main_window.match_existing_screen(frame, expected_id=expected_node_id)
            if actual_node_id == expected_node_id:
                expected_screen = self.flow_data.screens.get(expected_node_id)
                expected_name = expected_screen.name if expected_screen else "Unknown"
                logger.info(f"Successfully arrived at '{expected_name}'.")
                self.set_current_screen_id(actual_node_id, center=False)
                return

            time.sleep(VERIFY_ARRIVAL_INTERVAL_SEC)

        # Failed to verify after timeout
        actual_screen = self.flow_data.screens.get(actual_node_id)
        actual_name = actual_screen.name if actual_screen else "Unknown Screen"
        expected_screen = self.flow_data.screens.get(expected_node_id)
        expected_name = expected_screen.name if expected_screen else "Unknown"
        logger.warning(f"Arrival verification failed. Expected '{expected_name}', but arrived at '{actual_name}'.")

        fail_dir = self.main_window.session_dir / "failed_verifications"
        fail_dir.mkdir(exist_ok=True)
        fail_path = fail_dir / f"failed_{expected_name}_to_{actual_name}_{adb_utils.now_tag()}.png"
        cv2.imwrite(str(fail_path), frame)
        logger.info(f"Saved failed verification image to: {fail_path}")

        msg_box = QMessageBox(self); msg_box.setStyleSheet("QLabel{ color: black; }"); msg_box.setIcon(QMessageBox.Warning)
        msg_box.setText(f"Expected to arrive at '{expected_name}' but ended up at '{actual_name}'.")
        msg_box.setWindowTitle("Verification Failed"); msg_box.exec_()

    def find_all_paths(self, start_id: str, end_id: str) -> List[List[str]]:
        adj = {}
        for t in self.flow_data.transitions:
            if t.legacy: continue
            from_id, to_id = t.from_id, t.to_id
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
                transition = next((t for t in self.flow_data.transitions if t.from_id == path[i] and t.to_id == path[i+1]), None)

                if not transition or not (events := transition.touch_events) or transition.legacy:
                    is_valid = False
                    break

                segment_duration = max((e.time for e in events), default=0)
                total_cost += segment_duration
                events_by_segment.append(events)

            if is_valid:
                valid_paths_with_cost.append({"path": path, "cost": total_cost, "events_by_segment": events_by_segment})

        if not valid_paths_with_cost:
            target_screen = self.flow_data.screens.get(target_node_id)
            target_name = target_screen.name if target_screen else "Unknown"
            msg_box = QMessageBox(self); msg_box.setStyleSheet("QLabel{ color: black; }"); msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText(f"No valid replayable path found to '{target_name}'.")
            msg_box.setWindowTitle("Replay Warning"); msg_box.exec_()
            return

        best_path_info = min(valid_paths_with_cost, key=lambda p: p['cost'])

        final_event_list = []
        time_offset = 0.0
        for segment_events in best_path_info['events_by_segment']:
            segment_duration = 0.0
            for event in sorted(segment_events, key=lambda e: e.time):
                adjusted_event = event.__dict__.copy()
                adjusted_event['time'] = round(event.time + time_offset, 4)
                final_event_list.append(adjusted_event)
                segment_duration = max(segment_duration, event.time)
            time_offset += REPLAY_SEGMENT_GAP_SEC

        path_names = ' -> '.join((self.flow_data.screens.get(sid).name if self.flow_data.screens.get(sid) else sid) for sid in best_path_info['path'])
        print(f"Replaying lowest-cost path (Cost: {best_path_info['cost']:.2f}s): {path_names}")
        self.replay_path(final_event_list, final_node_id=best_path_info['path'][-1])

    def add_connection(self, from_id: str):
        screens = self.flow_data.screens
        items = [f"{info.name} ({sid})" for sid, info in screens.items() if sid != from_id]
        if not items: return
        item, ok = QInputDialog.getItem(self, "Add Connection", "Select destination:", items, 0, False)
        if ok and item:
            to_id = item.split('(')[-1].strip(')')
            if any(t.from_id == from_id and t.to_id == to_id for t in self.flow_data.transitions): return
            self.flow_data.transitions.append(Transition(from_id=from_id, to_id=to_id))
            if callable(self.on_save): self.on_save()
            self.update()

    def delete_connection(self, from_id: str, to_id: str):
        transitions = self.flow_data.transitions
        if (t_to_del := next((t for t in transitions if t.from_id == from_id and t.to_id == to_id), None)):
            transitions.remove(t_to_del)
            if callable(self.on_save): self.on_save()
            self.update()
            print(f"Deleted transition: {from_id} -> {to_id}")
