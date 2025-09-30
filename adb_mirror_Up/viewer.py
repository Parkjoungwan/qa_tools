import time, cv2, numpy as np, os, json
from typing import List, Optional, Tuple
from subprocess import run, PIPE
from pathlib import Path
from PyQt5.QtCore   import Qt, pyqtSignal
from PyQt5.QtGui    import QPainter, QColor, QPen
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit

class MultiViewer(QWidget):
    registration_required = pyqtSignal(object)

    def __init__(
        self,
        serials: List[str],
        win_name: str = "Android Mirror",
        log_fn=None,
        device_resolutions: dict = None,
        viewer_width_per_device: int = 1200,
        viewer_height: int = 750,
        samples_dir=None,
        fingerprints_dir=None,
    ):
        super().__init__()
        self.serials = serials; self.log_fn = log_fn
        self.device_res = device_resolutions or {}
        self.viewer_w, self.viewer_h = viewer_width_per_device, viewer_height
        self.samples_dir = samples_dir
        self.fingerprints_dir = fingerprints_dir

        self.setWindowTitle(win_name)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.viewer_w*len(serials), self.viewer_h)
        self.move(0,0); self.setFocusPolicy(Qt.StrongFocus)

        self._drag_serial=self._drag_start=self._drag_time=None
        self.tap_func=self.swipe_func=self.text_func=self.capture_func=self.page_rec_func=None
        self.adb_executing=False

        self.current_page_name = "unidentified"
        self.page_fingerprints = {}
        self.page_tap_coords = {} # For real-time deduplication
        self.load_page_fingerprints()
        self.load_tap_node_coords()

        self.registration_required.connect(self.register_new_page_prompt)

    def load_page_fingerprints(self):
        manifest_path = self.fingerprints_dir / "fingerprints.json"
        if not manifest_path.exists():
            self.page_fingerprints = {}
            return
        with open(manifest_path, 'r') as f:
            try: manifest = json.load(f)
            except json.JSONDecodeError: manifest = {}

        self.page_fingerprints = {}
        for page_name, template_files in manifest.items():
            self.page_fingerprints[page_name] = []
            for file in template_files:
                img_path = self.fingerprints_dir / file
                if img_path.exists():
                    self.page_fingerprints[page_name].append(cv2.imread(str(img_path)))
        print(f"Loaded {len(self.page_fingerprints)} page fingerprints.")

    def load_tap_node_coords(self):
        graph_path = Path(__file__).parent / 'visualization' / 'graph.json'
        self.page_tap_coords = {}
        if not graph_path.exists():
            return
        
        with open(graph_path, 'r') as f:
            try: data = json.load(f)
            except json.JSONDecodeError: return

        for node in data.get('nodes', []):
            if node.get('type') == 'tap':
                page_id = node.get('parent_page')
                if page_id not in self.page_tap_coords:
                    self.page_tap_coords[page_id] = []
                
                try:
                    # Label is like "(x,y)", so parse it
                    coords = node['label'].strip('()').split(',')
                    x = int(coords[0])
                    y = int(coords[1])
                    self.page_tap_coords[page_id].append({'x': x, 'y': y})
                except (ValueError, IndexError):
                    continue
        print(f"Loaded coordinates for {sum(len(v) for v in self.page_tap_coords.values())} existing tap nodes.")


    # ---------- paint --------------------------------------------
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for i,s in enumerate(self.serials):
            pen=QPen(QColor(0,255,0)); pen.setWidth(5); p.setPen(pen)
            p.drawRect(i*self.viewer_w,0,self.viewer_w,self.viewer_h)
            p.setPen(QColor(255,255,255))
            p.drawText(i*self.viewer_w+20,40,f"[{s}] click/drag, W for text, N for page")
            p.drawText(i*self.viewer_w+20,80,f"Page: {self.current_page_name}")
            if self.adb_executing:
                p.setPen(QColor(255,255,0))
                p.drawText(i*self.viewer_w+20,self.viewer_h-20,"Executing ADB...")

    # ---------- events ------------------------------------------- 
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape: QApplication.quit()
        elif e.key()==Qt.Key_W: self.handle_text_input()
        elif e.key()==Qt.Key_N: 
            if self.page_rec_func: self.page_rec_func(self)
        else: super().keyPressEvent(e)

    def handle_text_input(self):
        if not self.serials: return
        serial, ok = QInputDialog.getItem(self, "Select Device", "Enter text on:", self.serials, 0, False)
        if not ok or not serial: return
        text, ok = QInputDialog.getText(self, "Input Text", f"Enter text for {serial}:", QLineEdit.Normal, "")
        if ok and text and self.text_func:
            self.text_func(serial, text, self)
            if self.log_fn: self.log_fn("text", serial, text)

    def mousePressEvent(self,e):
        if e.button() not in (Qt.LeftButton,Qt.RightButton): return
        m=self._map_to_device(e.x(),e.y());
        if m is None: return
        idx,dx,dy=m; serial=self.serials[idx]
        if e.button()==Qt.LeftButton:
            self._drag_serial, self._drag_start, self._drag_time = serial,(dx,dy),time.perf_counter()
        else:
            if self.log_fn: self.log_fn("cap",serial)

    def mouseReleaseEvent(self,e):
        if e.button()!=Qt.LeftButton or self._drag_serial is None: return
        m=self._map_to_device(e.x(),e.y()); self._drag_serial=None
        if m is None: return
        idx,ex,ey=m; serial=self.serials[idx]
        sx,sy=self._drag_start
        dur=int((time.perf_counter()-self._drag_time)*1000)
        if abs(ex-sx)<3 and abs(ey-sy)<3:
            if self.tap_func: self.tap_func(serial,ex,ey,self)
            if self.log_fn : self.log_fn("tap",serial,ex,ey)
            if self.capture_func: self.capture_func(serial,ex,ey,self)
        else:
            if self.swipe_func: self.swipe_func(serial,sx,sy,ex,ey,max(dur,50),self)
            if self.log_fn: self.log_fn("swipe",serial,sx,sy,ex,ey,dur)

    def recognize_page(self, screenshot):
        MATCH_THRESHOLD = 0.9
        best_match_score = -1
        best_match_page = None

        for page_name, templates in self.page_fingerprints.items():
            if not templates: continue
            total_score = 0
            for template in templates:
                if template is None or template.size == 0 or screenshot is None or screenshot.size == 0: continue
                if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]: continue
                res = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(res)
                total_score += max_val
            avg_score = total_score / len(templates) if templates else 0
            if avg_score > best_match_score:
                best_match_score = avg_score
                best_match_page = page_name

        if best_match_score >= MATCH_THRESHOLD:
            self.current_page_name = best_match_page
            print(f"Page recognized as: {self.current_page_name} (Score: {best_match_score:.2f})")
        else:
            print(f"No matching page found (Best score: {best_match_score:.2f}). Starting registration.")
            self.registration_required.emit(screenshot)
        self.update()

    def register_new_page_prompt(self, screenshot):
        page_name, ok = QInputDialog.getText(self, "New Page Registration", "Enter a name for this new page:")
        if not ok or not page_name:
            print("Page registration cancelled.")
            return

        grid_prompt = "Select key areas for the fingerprint.\n+---+---+---+---+\n| 1 | 2 | 3 | 4 |\n+---+---+---+---+\n| 5 | 6 | 7 | 8 |\n+---+---+---+---+\n| 9 | 10| 11| 12|\n+---+---+---+---+\nEnter numbers (e.g., 1,4,9):"
        cell_str, ok = QInputDialog.getText(self, "Select Fingerprint Areas", grid_prompt)
        if not ok or not cell_str: 
            print("Page registration cancelled.")
            return
        
        try: cell_indices = [int(i.strip()) for i in cell_str.split(',')]
        except ValueError:
            print("Invalid input for cell numbers.")
            return

        h, w = screenshot.shape[:2]
        cell_h, cell_w = h // 3, w // 4
        template_files = []
        for idx in cell_indices:
            if not (1 <= idx <= 12): continue
            row, col = (idx - 1) // 4, (idx - 1) % 4
            y1, x1 = row * cell_h, col * cell_w
            y2, x2 = y1 + cell_h, x1 + cell_w
            template_img = screenshot[y1:y2, x1:x2]
            
            ts = int(time.time())
            template_filename = f"{page_name.replace(' ', '_')}_{idx}_{ts}.png"
            cv2.imwrite(str(self.fingerprints_dir / template_filename), template_img)
            template_files.append(template_filename)

        manifest_path = self.fingerprints_dir / "fingerprints.json"
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                try: manifest = json.load(f)
                except json.JSONDecodeError: manifest = {}
        
        manifest[page_name] = template_files
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"New page '{page_name}' registered with {len(template_files)} templates.")
        self.current_page_name = page_name
        self.load_page_fingerprints()

    def _map_to_device(self,x:int,y:int)->Optional[Tuple[int,int,int]]:
        for i,s in enumerate(self.serials):
            left=i*self.viewer_w
            if not (left<=x<left+self.viewer_w): continue
            if s not in self.device_res: return None
            dw,dh=self.device_res[s]
            scale=self.viewer_h/dh
            eff_w=dw*scale
            off_x=(self.viewer_w-eff_w)/2
            if not (off_x<=x-left<=off_x+eff_w): return None
            px=int((x-left-off_x)*dw/eff_w)
            py=int(y*dh/self.viewer_h)
            return i,px,py
        return None

# ---------- adb wrappers ----------------------------------------- 
def tap(serial,x,y,v):
    v.adb_executing=True; v.update()
    run(["adb","-s",serial,"shell","input","tap",str(x),str(y)])
    v.adb_executing=False; v.update()

def swipe(serial,x1,y1,x2,y2,d,v):
    v.adb_executing=True; v.update()
    run(["adb","-s",serial,"shell","input","swipe",str(x1),str(y1),str(x2),str(y2),str(d)])
    v.adb_executing=False; v.update()

def text(serial, text_to_input, v):
    v.adb_executing=True; v.update()
    run(["adb", "-s", serial, "shell", "input", "text", f"'{text_to_input}'"])
    v.adb_executing=False; v.update()

def capture_sample(serial, x, y, v, size=100):
    # 1. Deduplication Check
    MERGE_RADIUS = 50
    page_id = f"page_{v.current_page_name.replace(' ', '_')}"
    
    if page_id in v.page_tap_coords:
        for existing_tap in v.page_tap_coords[page_id]:
            dist = ((existing_tap['x'] - x)**2 + (existing_tap['y'] - y)**2)**0.5
            if dist < MERGE_RADIUS:
                print(f"📸 Skipping sample, duplicate of existing tap at ({existing_tap['x']},{existing_tap['y']}).")
                return

    v.adb_executing=True; v.update()
    try:
        result = run(["adb", "-s", serial, "shell", "screencap", "-p"], capture_output=True, check=True)
        png_data = result.stdout
        img_np = np.frombuffer(png_data, np.uint8)
        img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        if img is None:
            print(f"[{serial}] Failed to decode screenshot.")
            return

        h, w = img.shape[:2]
        half = size // 2
        x1, y1 = max(0, x - half), max(0, y - half)
        x2, y2 = min(w, x + half), min(h, y + half)
        cropped_img = img[y1:y2, x1:x2]

        if v.samples_dir:
            page_dir = v.samples_dir / v.current_page_name.replace(' ', '_')
            page_dir.mkdir(exist_ok=True)
            ts = int(time.time())
            filename = page_dir / f"{ts}_{serial}_{x}_{y}.png"
            cv2.imwrite(str(filename), cropped_img)
            print(f"📸 Sample saved: {filename.name}")

            # Add to in-memory list for current session
            if page_id not in v.page_tap_coords:
                v.page_tap_coords[page_id] = []
            v.page_tap_coords[page_id].append({'x': x, 'y': y})

    except Exception as e:
        print(f"[{serial}] Error capturing sample: {e}")
    finally:
        v.adb_executing=False; v.update()

def handle_page_recognition(v):
    v.adb_executing=True; v.update()
    try:
        serial = v.serials[0]
        result = run(["adb", "-s", serial, "shell", "screencap", "-p"], capture_output=True, check=True)
        png_data = result.stdout
        img_np = np.frombuffer(png_data, np.uint8)
        screenshot = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
        if screenshot is None:
            print(f"[{serial}] Failed to decode screenshot for page recognition.")
            return
        v.recognize_page(screenshot)
    except Exception as e:
        print(f"Error during page recognition: {e}")
    finally:
        v.adb_executing=False; v.update()
