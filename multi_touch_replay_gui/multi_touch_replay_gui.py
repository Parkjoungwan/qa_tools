#!/usr/bin/env python3
# gui_touch_replay.py
# ────────────────────────────────────────────────────────────────
# • Build & run multi-device touch/gesture queues
# • Progress bar + cycle counter
# • Persistent Favorites pane (save / load / delete)
# • Immediate Stop support

import subprocess, multiprocessing as mp, datetime, time, json, threading, copy
from pathlib import Path
from typing import List, Dict, Tuple, Union
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# ───────── replay core ──────────────────────────────────────────
Event   = Tuple[float, str, Tuple[Union[int, str], ...]]        # (elapsed, kind, args)
LogDict = Dict[str, List[Event]]

def load_events(path: Path) -> LogDict:
    evs: LogDict = {}
    with path.open() as f:
        f.readline()  # Skip header
        for ln in f:
            if not ln.strip():
                continue
            p = ln.strip().split('\t')
            kind, t, serial = p[0], float(p[1]), p[2]
            
            args: Tuple[Union[int, str], ...] = ()
            if kind == "tap":
                args = tuple(map(int, p[4:6]))
            elif kind == "swipe":
                args = tuple(map(int, p[4:9]))
            elif kind == "text":
                args = (p[3],)
            elif kind == "cap":
                args = ()
            
            evs.setdefault(serial, []).append((t, kind, args))

    if not evs:
        raise ValueError(f"{path}: no valid events")
    for v in evs.values():
        v.sort(key=lambda e: e[0])
    return evs

def adb(serial, *cmd, capture=False):
    full = ["adb", "-s", serial, *map(str, cmd)]
    if capture:
        return subprocess.check_output(full)
    subprocess.check_call(full,
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)

def save_cap(serial: str, dest: Path):
    dest.write_bytes(adb(serial, "exec-out", "screencap", "-p", capture=True))

def worker(serial: str, evs: List[Event], start: float, out_dir: Union[Path, None]):
    for t, kind, args in evs:
        time.sleep(max(0, start + t - time.time()))
        if kind == "tap":
            x, y = args
            adb(serial, "shell", "input", "tap", x, y)
        elif kind == "swipe":
            x1, y1, x2, y2, dur = args
            adb(serial, "shell", "input", "swipe", x1, y1, x2, y2, dur)
        elif kind == "text":
            text, = args
            adb(serial, "shell", "input", "text", f"'{text}'")
        elif kind == "cap":
            if out_dir:
                save_cap(serial, out_dir / f"{serial}_{t:.2f}.png")

def replay_once(path: Path, stop_evt: threading.Event) -> bool:
    evs = load_events(path)

    has_cap = any(e[1] == "cap" for ev_list in evs.values() for e in ev_list)
    out_dir = None
    if has_cap:
        out_dir = Path("log_images") / f"{path.stem}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
        out_dir.mkdir(parents=True, exist_ok=True)

    start = time.time() + 1
    procs = [mp.Process(target=worker, args=(s, e, start, out_dir))
             for s, e in evs.items()]
    for p in procs:
        p.start()

    while procs and not stop_evt.is_set():
        for p in procs[:]:
            p.join(timeout=0.1)
            if not p.is_alive():
                procs.remove(p)

    if stop_evt.is_set():
        for p in procs:
            p.terminate(); p.join()
        return False
    return True

# queue item types
LogItem   = Tuple[str, Path, int, float]   # ("log", path, repeat, gap)
GapItem   = Tuple[str, float]              # ("gap", gap_sec)
QueueItem = Union[LogItem, GapItem]

def sleep_cancel(sec: float, evt: threading.Event):
    end = time.time() + sec
    while not evt.is_set() and time.time() < end:
        time.sleep(min(0.1, end - time.time()))

def play_queue(queue: List[QueueItem], cycles: int,
               stop_evt: threading.Event,
               progress_cb, done_cb):
    try:
        for c in range(cycles):
            if stop_evt.is_set():
                break
            progress_cb(c + 1, cycles)         # progress update
            for item in queue:
                if stop_evt.is_set():
                    break
                if item[0] == "log":
                    _, path, rep, gap = item
                    for i in range(rep):
                        if stop_evt.is_set():
                            break
                        if not replay_once(path, stop_evt):
                            break
                        if (i != rep - 1 or gap > 0):
                            sleep_cancel(gap, stop_evt)
                else:
                    _, gap = item
                    sleep_cancel(gap, stop_evt)
        done_cb(True, "Stopped" if stop_evt.is_set() else "Finished")
    except Exception as e:
        done_cb(False, str(e))

# ───────── GUI ────────────────────────────────────────────────
FAV_FILE = Path(__file__).resolve().parent / "favorites.json"

class ReplayGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Touch Log Replayer")

        self.queue: List[QueueItem] = []
        self.favorites: List[Tuple[str, List[QueueItem]]] = self._load_fav_file()

        self.stop_evt = threading.Event()
        self.fav_visible = False

        self._build()
        self._populate_fav_listbox()

    # ---------- UI ----------
    def _build(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.grid(sticky="nsew")

        # file controls
        self.path_var = tk.StringVar()
        ttk.Entry(frm, textvariable=self.path_var, width=44)\
            .grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Button(frm, text="Browse", command=self._browse)\
            .grid(row=0, column=4, padx=4)

        ttk.Label(frm, text="Repeat").grid(row=1, column=0, sticky="e")
        self.rep_var = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=1, to=99, textvariable=self.rep_var, width=5)\
            .grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="Gap(s)").grid(row=1, column=2, sticky="e")
        self.gap_var = tk.DoubleVar(value=1.0)
        ttk.Entry(frm, textvariable=self.gap_var, width=6)\
            .grid(row=1, column=3, sticky="w")

        self.add_btn = ttk.Button(frm, text="Add", command=self._add_log)
        self.add_gap_btn = ttk.Button(frm, text="Add Gap", command=self._add_gap)
        self.add_btn.grid(row=1, column=4, padx=6)
        self.add_gap_btn.grid(row=1, column=5, padx=2)

        # queue Treeview
        cols = ("type", "file / gap", "rep", "gap")
        self.tree = ttk.Treeview(frm, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (60, 240, 40, 60)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.grid(row=2, column=0, columnspan=6, pady=6, sticky="nsew")

        # edit buttons
        ed = ttk.Frame(frm); ed.grid(row=3, column=0, columnspan=6)
        self.up_btn   = ttk.Button(ed, text="Up",   command=lambda: self._move(-1))
        self.down_btn = ttk.Button(ed, text="Down", command=lambda: self._move(1))
        self.del_btn  = ttk.Button(ed, text="Delete", command=self._delete)
        self.up_btn.grid(row=0, column=0, padx=2)
        self.down_btn.grid(row=0, column=1, padx=2)
        self.del_btn.grid(row=0, column=2, padx=2)

        ttk.Label(frm, text="Cycle Repeat").grid(row=4, column=0, sticky="e")
        self.cycle_var = tk.IntVar(value=1)
        ttk.Spinbox(frm, from_=1, to=99, textvariable=self.cycle_var, width=5)\
            .grid(row=4, column=1, sticky="w")

        self.run_btn  = ttk.Button(frm, text="Run",  command=self._run)
        self.stop_btn = ttk.Button(frm, text="Stop", command=self._stop, state="disabled")
        self.fav_add  = ttk.Button(frm, text="★ Favorite", command=self._save_fav)
        self.fav_toggle = ttk.Button(frm, text="Favorites ▶", command=self._toggle_fav)
        self.run_btn.grid(row=4, column=3, pady=8)
        self.stop_btn.grid(row=4, column=4, pady=8)
        self.fav_add.grid(row=4, column=5, pady=8)
        self.fav_toggle.grid(row=0, column=6, rowspan=2, sticky="ns")

        # progress bar
        self.prog = ttk.Progressbar(frm, mode="determinate", length=200)
        self.prog.grid(row=5, column=0, columnspan=4, sticky="we", pady=(6, 0))
        self.prog_lbl = ttk.Label(frm, text="")
        self.prog_lbl.grid(row=5, column=4, columnspan=2, sticky="e")

        # favorites side panel
        self.fav_frame = ttk.Frame(self.root, padding=6, relief="ridge")
        ttk.Label(self.fav_frame, text="Favorites").pack()
        self.fav_list = tk.Listbox(self.fav_frame, width=25, height=14)
        self.fav_list.pack(fill="both", expand=True)
        self.fav_list.bind("<Double-1>", self._load_fav)

        # Delete button inside favorites panel
        self.fav_del = ttk.Button(self.fav_frame, text="Delete",
                                  command=self._delete_fav)
        self.fav_del.pack(fill="x", pady=(6, 0))

        # layout weights
        self.root.columnconfigure(0, weight=1)
        for i in range(6):
            frm.columnconfigure(i, weight=1)
        frm.rowconfigure(2, weight=1)

    # ---------- queue operations ----------
    def _browse(self):
        p = filedialog.askopenfilename(filetypes=[("Log", "*.log"), ("All", "*.*")])
        if p:
            self.path_var.set(p)

    def _add_log(self, path: Path | None = None):
        p = Path(path or self.path_var.get())
        if not p.exists():
            messagebox.showerror("Error", "File not found")
            return
        rep = self.rep_var.get(); gap = self.gap_var.get()
        self.queue.append(("log", p, rep, gap))
        self.tree.insert("", tk.END, values=("log", p.name, rep, gap))

    def _add_gap(self):
        gap = self.gap_var.get()
        self.queue.append(("gap", gap))
        self.tree.insert("", tk.END, values=("gap", f"{gap}s", "-", gap))

    def _move(self, d: int):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        new = idx + d
        if 0 <= new < len(self.queue):
            self.queue[idx], self.queue[new] = self.queue[new], self.queue[idx]
            vals = self.tree.item(sel[0])["values"]
            self.tree.delete(sel[0])
            self.tree.insert("", new, values=vals)
            self.tree.selection_set(self.tree.get_children()[new])

    def _delete(self):
        sel = self.tree.selection()
        if sel:
            idx = self.tree.index(sel[0])
            self.queue.pop(idx)
            self.tree.delete(sel[0])

    # ---------- run / stop ----------
    def _run(self):
        if not self.queue:
            messagebox.showinfo("Info", "Queue is empty")
            return
        for b in (self.run_btn, self.add_btn, self.add_gap_btn,
                  self.up_btn, self.down_btn, self.del_btn, self.fav_add):
            b.state(["disabled"])
        self.stop_btn.state(["!disabled"])
        self.tree.configure(selectmode="none")
        self.stop_evt.clear()

        cycles = self.cycle_var.get()
        self.prog["maximum"] = cycles; self.prog["value"] = 0
        self.prog_lbl.config(text=f"0 / {cycles}")

        threading.Thread(target=play_queue,
                         args=(self.queue, cycles,
                               self.stop_evt,
                               self._progress_update,
                               self._done),
                         daemon=True).start()

    def _stop(self):
        self.stop_evt.set()

    def _progress_update(self, cur: int, total: int):
        self.root.after(0, lambda: (
            self.prog.config(value=cur),
            self.prog_lbl.config(text=f"{cur} / {total}")
        ))

    def _done(self, ok: bool, msg: str):
        def ui():
            for b in (self.run_btn, self.add_btn, self.add_gap_btn,
                      self.up_btn, self.down_btn, self.del_btn, self.fav_add):
                b.state(["!disabled"])
            self.stop_btn.state(["disabled"])
            self.tree.configure(selectmode="browse")
            self.prog["value"] = 0
            self.prog_lbl.config(text="")
            (messagebox.showinfo if ok else messagebox.showerror)("Done", msg)
        self.root.after(0, ui)

    # ---------- favorites (save/load/delete) ----------
    def _serialize_item(self, it: QueueItem):
        return ["log", str(it[1]), it[2], it[3]] if it[0] == "log" else ["gap", it[1]]

    def _deserialize_item(self, data) -> QueueItem:
        return ("log", Path(data[1]), data[2], data[3]) if data[0] == "log" else ("gap", data[1])

    def _load_fav_file(self):
        if not FAV_FILE.exists():
            return []
        try:
            raw = json.loads(FAV_FILE.read_text())
            return [(ent["name"], [self._deserialize_item(d) for d in ent["queue"]])
                    for ent in raw]
        except Exception:
            messagebox.showwarning("Warning", "favorites.json corrupted")
            return []

    def _save_fav_file(self):
        data = [{"name": n, "queue": [self._serialize_item(it) for it in q]}
                for n, q in self.favorites]
        try:
            FAV_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            messagebox.showerror("Error", f"Save failed:\n{e}")

    def _populate_fav_listbox(self):
        self.fav_list.delete(0, tk.END)
        for n, _ in self.favorites:
            self.fav_list.insert(tk.END, n)

    def _save_fav(self):
        if not self.queue:
            messagebox.showinfo("Info", "Queue is empty")
            return
        name = simpledialog.askstring("Favorite name", "Enter name:",
                                      initialvalue=f"Fav {len(self.favorites) + 1}")
        if not name:
            return
        self.favorites.append((name, copy.deepcopy(self.queue)))
        self._populate_fav_listbox()
        self._save_fav_file()
        messagebox.showinfo("Saved", f"Saved '{name}'")

    def _delete_fav(self):
        sel = self.fav_list.curselection()
        if not sel:
            messagebox.showinfo("Info", "Select an item to delete.")
            return
        idx = sel[0]
        name, _ = self.favorites[idx]
        if not messagebox.askyesno("Delete", f"Delete favorite '{name}'?"):
            return
        self.favorites.pop(idx)
        self._populate_fav_listbox()
        self._save_fav_file()

    def _toggle_fav(self):
        if self.fav_visible:
            self.fav_frame.grid_forget()
            self.fav_toggle.config(text="Favorites ▶")
        else:
            self.fav_frame.grid(row=0, column=6, rowspan=6, sticky="ns")
            self.fav_toggle.config(text="Hide ◀")
        self.fav_visible = not self.fav_visible

    def _load_fav(self, _event):
        def _do():
            sel = self.fav_list.curselection()
            if not sel:
                return
            idx = sel[0]
            name, queue = copy.deepcopy(self.favorites[idx])
            self.queue = queue
            self.tree.delete(*self.tree.get_children())
            for it in self.queue:
                if it[0] == "log":
                    _, p, rep, gap = it
                    self.tree.insert("", tk.END, values=("log", p.name, rep, gap))
                else:
                    _, gap = it
                    self.tree.insert("", tk.END, values=("gap", f"{gap}s", "-", gap))
            messagebox.showinfo("Loaded", f"Loaded '{name}'")
        self.root.after_idle(_do)

    # ---------- mainloop ----------
    def start(self):
        self.root.mainloop()


if __name__ == "__main__":
    ReplayGUI().start()

