import time, cv2, numpy as np, os, json
from typing import List, Optional, Tuple
from subprocess import run, PIPE
from pathlib import Path
from PyQt5.QtCore   import Qt, pyqtSignal
from PyQt5.QtGui    import QPainter, QColor, QPen
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QMessageBox

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
        self.tap_func=self.swipe_func=self.text_func=self.capture_func=self.page_rec_func=self.save_log_func=self.scan_pagination_func=self.go_to_page_func=None
        self.adb_executing=False

        self.current_page_name = "unidentified"
        self.main_page_current_pagination = 1
        self.page_fingerprints = {}
        self.page_tap_coords = {}
        self.load_page_fingerprints()
        self.load_tap_node_coords()

        self.pagination_reg_step = 0
        self.pagination_info = {}
        self.pagination_page_images = []
        self.reg_message = ""

        self.registration_required.connect(self.register_new_page_prompt)
        self.load_pagination_info("mainPage") # Load mainPage pagination info at startup

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
                    coords = node['label'].strip('()').split(',')
                    x = int(coords[0])
                    y = int(coords[1])
                    self.page_tap_coords[page_id].append({'x': x, 'y': y})
                except (ValueError, IndexError):
                    continue
        print(f"Loaded coordinates for {sum(len(v) for v in self.page_tap_coords.values())} existing tap nodes.")

    def load_pagination_info(self, base_page_name):
        self.pagination_info = {}
        self.pagination_page_images = []
        pagination_dir = self.fingerprints_dir / f"pagination_{base_page_name}"
        info_path = pagination_dir / "pagination_info.json"
        if not info_path.exists():
            print(f"[DEBUG] No pagination_info.json found for {base_page_name}.")
            return
        
        with open(info_path, 'r') as f:
            try: self.pagination_info = json.load(f)
            except json.JSONDecodeError: return

        for i in range(1, 51):
            p = pagination_dir / f"page_{i}.png"
            if not p.exists(): break
            img = cv2.imread(str(p))
            if img is not None and img.size > 0:
                self.pagination_page_images.append(img)
            else:
                print(f"[DEBUG] Failed to load pagination image: {p.name}")
        print(f"[DEBUG] Loaded {len(self.pagination_page_images)} pagination page images for {base_page_name}.")

    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for i,s in enumerate(self.serials):
            pen=QPen(QColor(0,255,0)); pen.setWidth(5); p.setPen(pen)
            p.drawRect(i*self.viewer_w,0,self.viewer_w,self.viewer_h)
            p.setPen(QColor(255,255,255))
            p.drawText(i*self.viewer_w+20,40,f"[{s}] G-GoTo, P-Pagination, N-Page, S-Save")
            p.drawText(i*self.viewer_w+20,80,f"Page: {self.current_page_name}")
            if self.adb_executing:
                p.setPen(QColor(255,255,0))
                p.drawText(i*self.viewer_w+20,self.viewer_h-20,"Executing ADB...")
            if self.reg_message:
                p.setPen(QColor(0,255,255))
                p.drawText(i*self.viewer_w+20,self.viewer_h-40, self.reg_message)

        # Dim overlay when adb_executing is True
        if self.adb_executing:
            p.fillRect(self.rect(), QColor(0, 0, 0, 128)) # Semi-transparent black

    def keyPressEvent(self,e):
        if self.adb_executing: return # Block input when ADB is executing

        if self.pagination_reg_step == 5 and e.key() == Qt.Key_S:
            if self.scan_pagination_func: self.scan_pagination_func()
            return

        if e.key()==Qt.Key_Escape: QApplication.quit()
        elif e.key()==Qt.Key_W: self.handle_text_input()
        elif e.key()==Qt.Key_N: 
            if self.page_rec_func: self.page_rec_func(self)
        elif e.key()==Qt.Key_S:
            if self.save_log_func: self.save_log_func()
        elif e.key()==Qt.Key_P:
            self.start_pagination_registration()
        elif e.key()==Qt.Key_G:
            self.handle_go_to_page()
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
        if self.adb_executing: return # Block input when ADB is executing

        if self.pagination_reg_step > 0:
            m=self._map_to_device(e.x(),e.y());
            if m is None: return
            _, x, y = m
            if self.pagination_reg_step == 1: # Area Top-Left
                self.pagination_info['area'] = {'x1': x, 'y1': y}
                self.pagination_reg_step = 2
                self.reg_message = "Click pagination area BOTTOM-RIGHT corner."
            elif self.pagination_reg_step == 2: # Area Bottom-Right
                self.pagination_info['area']['x2'] = x
                self.pagination_info['area']['y2'] = y
                self.pagination_reg_step = 3
                self.reg_message = "Click the LEFT pagination button."
            elif self.pagination_reg_step == 3: # Left button
                self.pagination_info['left_button'] = {'x': x, 'y': y}
                self.pagination_reg_step = 4
                self.reg_message = "Click the RIGHT pagination button."
            elif self.pagination_reg_step == 4: # Right button
                self.pagination_info['right_button'] = {'x': x, 'y': y}
                # CRITICAL: Save info and load it immediately after all clicks are done
                self.save_pagination_info()
                base_page_name = self.current_page_name.split('_')[0]
                self.load_pagination_info(base_page_name) # Load newly saved info
                self.pagination_reg_step = 5
                self.reg_message = "Go to FIRST page, then press S to start scanning."
                self.adb_executing = False # Release block after registration clicks
            self.update()
            return

        if e.button() not in (Qt.LeftButton,Qt.RightButton): return
        m=self._map_to_device(e.x(),e.y());
        if m is None: return
        idx,dx,dy=m; serial=self.serials[idx]
        if e.button()==Qt.LeftButton:
            self._drag_serial, self._drag_start, self._drag_time = serial,(dx,dy),time.perf_counter()
        else:
            if self.log_fn: self.log_fn("cap",serial)

    def mouseReleaseEvent(self,e):
        if self.adb_executing: return # Block input when ADB is executing
        if self.pagination_reg_step > 0: return
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

    def start_pagination_registration(self):
        if self.current_page_name == "unidentified":
            msgBox = QMessageBox()
            msgBox.setText("Current page is unidentified. Page registration must be completed first.")
            msgBox.setInformativeText("Starting page registration process...")
            msgBox.setStandardButtons(QMessageBox.Ok)
            msgBox.exec_()
            if self.page_rec_func: self.page_rec_func(self)
            return # Wait for page registration to complete

        self.pagination_reg_step = 1
        self.pagination_info = {}
        self.reg_message = "Click pagination area TOP-LEFT corner."
        self.update()

    def save_pagination_info(self):
        base_page_name = self.current_page_name.split('_')[0]
        self.pagination_info['owner_page'] = base_page_name

        pagination_dir = self.fingerprints_dir / f"pagination_{base_page_name}"
        pagination_dir.mkdir(exist_ok=True)
        filepath = pagination_dir / "pagination_info.json"
        
        print(f"[DEBUG] Attempting to save pagination info to: {filepath}")
        print(f"[DEBUG] Pagination info content: {self.pagination_info}")

        try:
            with open(filepath, 'w') as f:
                json.dump(self.pagination_info, f, indent=2)
            print(f"Pagination info for {base_page_name} saved to {filepath}")
        except Exception as e:
            print(f"[ERROR] Failed to save pagination info: {e}")

        self.pagination_reg_step = 0 # This will be set to 5 in mousePressEvent
        self.reg_message = ""
        self.update()

    def recognize_page(self, screenshot):
        best_match_score = -1
        best_match_page = None
        MATCH_THRESHOLD = 0.9

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
            # Check if this page has pagination info
            pagination_info_path = self.fingerprints_dir / f"pagination_{best_match_page}" / "pagination_info.json"
            if pagination_info_path.exists():
                self.recognize_pagination_state(screenshot, best_match_page)
            else:
                self.current_page_name = best_match_page
            print(f"Page recognized as: {self.current_page_name} (Score: {best_match_score:.2f})")
        else:
            print(f"No matching page found (Best score: {best_match_score:.2f}). Starting registration.")
            self.registration_required.emit(screenshot)
        self.update()

    def recognize_pagination_state(self, screenshot, base_page_name):
        pagination_dir = self.fingerprints_dir / f"pagination_{base_page_name}"
        info_path = pagination_dir / "pagination_info.json"
        if not info_path.exists():
            self.current_page_name = f"{base_page_name}_1"
            return

        # Use pre-loaded pagination info and images
        area = self.pagination_info['area']
        page_images = self.pagination_page_images

        if not page_images: 
            print("[DEBUG] No page images loaded for pagination recognition.")
            self.current_page_name = f"{base_page_name}_1"
            return

        print(f"[DEBUG] Loaded {len(page_images)} pagination page images for {base_page_name}.")
        current_pagination_area = screenshot[area['y1']:area['y2'], area['x1']:area['x2']]
        if current_pagination_area is None or current_pagination_area.size == 0:
            print("[DEBUG] Current pagination area is empty or invalid.")
            self.current_page_name = f"{base_page_name}_1"
            return

        best_match = -1
        current_page = 1
        for i, page_img in enumerate(page_images):
            if page_img is None or page_img.size == 0: 
                print(f"[DEBUG] Skipping empty page_img for index {i+1}.")
                continue
            res = cv2.matchTemplate(current_pagination_area, page_img, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            print(f"[DEBUG] Page {i+1} match score: {max_val:.2f}")
            if max_val > best_match:
                best_match = max_val
                current_page = i + 1
        
        self.current_page_name = f"{base_page_name}_{current_page}"

    def register_new_page_prompt(self, screenshot):
        page_name_input, ok = QInputDialog.getText(self, "New Page Registration", "Enter a name for this new page:")
        if not ok or not page_name_input:
            print("Page registration cancelled.")
            return

        # Force mainPage variations to be stored under a single fingerprint
        page_name_for_fingerprint = "mainPage" if page_name_input.startswith("mainPage") else page_name_input

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
            template_filename = f"{page_name_for_fingerprint.replace(' ', '_')}_{idx}_{ts}.png"
            cv2.imwrite(str(self.fingerprints_dir / template_filename), template_img)
            template_files.append(template_filename)

        manifest_path = self.fingerprints_dir / "fingerprints.json"
        manifest = {}
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                try: manifest = json.load(f)
                except json.JSONDecodeError: manifest = {}
        
        # Append to existing templates if page_name_for_fingerprint already exists
        if page_name_for_fingerprint in manifest:
            manifest[page_name_for_fingerprint].extend(template_files)
        else:
            manifest[page_name_for_fingerprint] = template_files

        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        print(f"New page '{page_name_input}' registered with fingerprint '{page_name_for_fingerprint}'.")
        self.current_page_name = page_name_input
        self.load_page_fingerprints()

    def handle_go_to_page(self):
        target_page, ok = QInputDialog.getInt(self, "Go to Page", "Enter target page number:", 1, 1, 100)
        if ok and self.go_to_page_func:
            self.go_to_page_func(target_page)

    def go_to_page(self, target_page):
        print(f"Attempting to go to page {target_page}...")
        self.reg_message = f"Moving to page {target_page}..."
        self.update()

        base_page_name = self.current_page_name.split('_')[0]
        self.load_pagination_info(base_page_name) # Load latest pagination info for the current base page

        if not self.pagination_info or not self.pagination_page_images:
            print(f"Pagination info or images not found for {base_page_name}. Please register first.")
            self.reg_message = f"Pagination for {base_page_name} not registered. Press P to start."
            self.update()
            return

        area = self.pagination_info['area']
        
        try:
            self.recognize_pagination_state(cv2.imdecode(np.frombuffer(run(["adb", "-s", self.serials[0], "shell", "screencap", "-p"], capture_output=True, check=True).stdout, np.uint8), cv2.IMREAD_COLOR), base_page_name)
            current_page_str = self.current_page_name.split('_')[-1]
            current_page = int(current_page_str) if current_page_str.isdigit() else 1
            print(f"Currently at {self.current_page_name}")

            diff = target_page - current_page
            if diff != 0:
                button_key = 'right_button' if diff > 0 else 'left_button'
                button_coords = self.pagination_info[button_key]
                for _ in range(abs(diff)):
                    print(f"Tapping {button_key}...")
                    run(["adb", "-s", self.serials[0], "shell", "input", "tap", str(button_coords['x']), str(button_coords['y'])])
                    time.sleep(1)
            
            self.main_page_current_pagination = target_page # Keep this for internal tracking
            self.current_page_name = f"{base_page_name}_{target_page}"
            self.reg_message = f"Arrived at page {target_page}."

        except Exception as e:
            print(f"Error during page navigation: {e}")
            self.reg_message = "Error during navigation."
        
        self.update()

    def scan_pagination_pages(self):
        print("Starting pagination scan...")
        self.reg_message = "Scanning... Please wait."
        self.update()

        serial = self.serials[0]
        base_page_name = self.current_page_name.split('_')[0]
        self.load_pagination_info(base_page_name) # Ensure pagination info is loaded

        if not self.pagination_info:
            print("Error: Pagination info not found. Please complete registration first.")
            self.reg_message = "Error: Pagination info incomplete."
            self.update()
            return

        pagination_dir = self.fingerprints_dir / f"pagination_{base_page_name}"
        pagination_dir.mkdir(exist_ok=True) # Ensure directory exists before saving images
        area = self.pagination_info['area']
        right_btn = self.pagination_info['right_button']

        prev_img = None
        for i in range(1, 50):
            try:
                result = run(["adb", "-s", serial, "shell", "screencap", "-p"], capture_output=True, check=True)
                img_np = np.frombuffer(result.stdout, np.uint8)
                img = cv2.imdecode(img_np, cv2.IMREAD_COLOR)
                if img is None: break

                cropped = img[area['y1']:area['y2'], area['x1']:area['x2']]

                if prev_img is not None:
                    res = cv2.matchTemplate(prev_img, cropped, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val > 0.98:
                        print("End of pagination detected.")
                        break
                
                # Save image
                filepath = pagination_dir / f"page_{i}.png"
                if cropped is not None and cropped.size > 0:
                    cv2.imwrite(str(filepath), cropped)
                    print(f"[DEBUG] Saved page {i} to {filepath.name}. Image size: {cropped.shape}")
                else:
                    print(f"[DEBUG] Cropped image for page {i} is empty or invalid. Not saving.")
                    break # Stop if image is invalid
                prev_img = cropped

                run(["adb", "-s", serial, "shell", "input", "tap", str(right_btn['x']), str(right_btn['y'])])
                time.sleep(1)

            except Exception as e:
                print(f"Error during scan: {e}")
                break
        
        self.save_pagination_info()

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
        if img is None: return

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
        if screenshot is None: return
        v.recognize_page(screenshot)
    except Exception as e:
        print(f"Error during page recognition: {e}")
    finally:
        v.adb_executing=False; v.update()