import time
from typing import List, Optional, Tuple
from subprocess import run
from PyQt5.QtCore   import Qt
from PyQt5.QtGui    import QPainter, QColor, QPen
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit

class MultiViewer(QWidget):
    def __init__(
        self,
        serials: List[str],
        win_name: str = "Android Mirror",
        log_fn=None,
        device_resolutions: dict = None,
        viewer_width_per_device: int = 1200,
        viewer_height: int = 750,
    ):
        super().__init__()
        self.serials = serials; self.log_fn = log_fn
        self.device_res = device_resolutions or {}
        self.viewer_w, self.viewer_h = viewer_width_per_device, viewer_height

        self.setWindowTitle(win_name)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(self.viewer_w*len(serials), self.viewer_h)
        self.move(0,0); self.setFocusPolicy(Qt.StrongFocus)

        self._drag_serial=self._drag_start=self._drag_time=None
        self.tap_func=self.swipe_func=self.text_func=None; self.adb_executing=False

    # ---------- paint --------------------------------------------
    def paintEvent(self,_):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        for i,s in enumerate(self.serials):
            pen=QPen(QColor(0,255,0)); pen.setWidth(5); p.setPen(pen)
            p.drawRect(i*self.viewer_w,0,self.viewer_w,self.viewer_h)
            p.setPen(QColor(255,255,255))
            p.drawText(i*self.viewer_w+20,40,f"[{s}] click/drag, W for text")
            if self.adb_executing:
                p.setPen(QColor(255,255,0))
                p.drawText(i*self.viewer_w+20,self.viewer_h-20,"Executing ADB...")

    # ---------- events -------------------------------------------
    def keyPressEvent(self,e):
        if e.key()==Qt.Key_Escape: QApplication.quit()
        elif e.key()==Qt.Key_W: self.handle_text_input()
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
        m=self._map_to_device(e.x(),e.y());  # idx,dx,dy or None
        if m is None: return
        idx,dx,dy=m; serial=self.serials[idx]
        if e.button()==Qt.LeftButton:
            self._drag_serial, self._drag_start, self._drag_time =                 serial,(dx,dy),time.perf_counter()
        else:
            if self.log_fn: self.log_fn("cap",serial)

    def mouseReleaseEvent(self,e):
        if e.button()!=Qt.LeftButton or self._drag_serial is None: return
        m=self._map_to_device(e.x(),e.y());  self._drag_serial=None
        if m is None: return
        idx,ex,ey=m; serial=self.serials[idx]
        sx,sy=self._drag_start
        dur=int((time.perf_counter()-self._drag_time)*1000)
        if abs(ex-sx)<3 and abs(ey-sy)<3:
            if self.tap_func: self.tap_func(serial,ex,ey,self)
            if self.log_fn : self.log_fn("tap",serial,ex,ey)
        else:
            if self.swipe_func:
                self.swipe_func(serial,sx,sy,ex,ey,max(dur,50),self)
            if self.log_fn:
                self.log_fn("swipe",serial,sx,sy,ex,ey,dur)

    # ---------- mapping ------------------------------------------
    def _map_to_device(self,x:int,y:int)->Optional[Tuple[int,int,int]]:
        for i,s in enumerate(self.serials):
            left=i*self.viewer_w
            if not (left<=x<left+self.viewer_w): continue
            if s not in self.device_res: return None
            dw,dh=self.device_res[s]        # 1920×1200

            scale=self.viewer_h/dh          # 600/1200 = 0.5
            eff_w=dw*scale                  # 960
            off_x=(self.viewer_w-eff_w)/2   # 0

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
    run(["adb","-s",serial,"shell","input","swipe",
         str(x1),str(y1),str(x2),str(y2),str(d)])
    v.adb_executing=False; v.update()

def text(serial, text_to_input, v):
    v.adb_executing=True; v.update()
    run(["adb", "-s", serial, "shell", "input", "text", f'"{text_to_input}"'])
    v.adb_executing=False; v.update()

