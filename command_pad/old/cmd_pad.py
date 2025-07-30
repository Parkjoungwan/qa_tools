#!/usr/bin/env python3
# cmd_buttons.py  – full-width buttons, scroll, process-aware status/lock

import json, subprocess, shlex, tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path

SAVE_FILE = Path(__file__).with_suffix(".json")


class CmdPad(tk.Tk):
    ROW_VISIBLE = 5
    BTN_HEIGHT = 40

    def __init__(self):
        super().__init__()
        self.title("Command Pad")
        self.commands: list[tuple[str, str]] = []
        self.btn_widgets: list[ttk.Button] = []
        self.current_proc: subprocess.Popen | None = None
        self._build_ui()
        self._load()

    # ---------- UI ----------
    def _build_ui(self):
        c_height = self.ROW_VISIBLE * self.BTN_HEIGHT + 8
        self.canvas = tk.Canvas(self, height=c_height, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical",
                            command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")

        # sync width & scrollregion
        self.inner.bind("<Configure>",
                        lambda _: self.canvas.configure(
                            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(
                             self.window_id, width=e.width))

        self._bind_mousewheel()

        add_btn = ttk.Button(self, text="＋", width=3, command=self._add_cmd)
        add_btn.grid(row=1, column=0, sticky="e", padx=10, pady=(6, 10))

        self.status = ttk.Label(self, text="", anchor="w")
        self.status.grid(row=2, column=0, columnspan=2,
                         sticky="we", padx=10, pady=(0, 8))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def _bind_mousewheel(self):
        self.canvas.bind_all("<MouseWheel>",
                             self._on_mousewheel)          # Win/mac
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)   # Linux
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _on_mousewheel(self, ev):
        if ev.num == 4 or ev.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        elif ev.num == 5 or ev.delta < 0:
            self.canvas.yview_scroll(1, "units")

    # ---------- command list ----------
    def _add_cmd(self):
        name = simpledialog.askstring("Name", "Button name:")
        if not name:
            return
        cmd = simpledialog.askstring("Command",
                                     f"Shell command for '{name}':")
        if not cmd:
            return
        self.commands.append((name, cmd))
        self._make_button(name, cmd)
        self._save()

    def _make_button(self, name: str, cmd: str):
        btn = ttk.Button(self.inner, text=name,
                         command=lambda n=name, c=cmd: self._run(n, c))
        btn.pack(fill="x", padx=16, pady=4)
        self.btn_widgets.append(btn)

    # ---------- run / monitor ----------
    def _run(self, name: str, cmd: str):
        if self.current_proc and self.current_proc.poll() is None:
            return  # still running
        try:
            self.current_proc = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Command not found: {cmd}")
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        for b in self.btn_widgets:
            b.state(["disabled"])
        self.status.config(text=f"▶ '{name}' 실행중…")
        self.after(500, self._check_proc)

    def _check_proc(self):
        if self.current_proc and self.current_proc.poll() is None:
            # still running → re-schedule
            self.after(500, self._check_proc)
        else:
            self._unlock()

    def _unlock(self):
        for b in self.btn_widgets:
            b.state(["!disabled"])
        self.status.config(text="완료")
        self.after(3000, lambda: self.status.config(text=""))  # 3 s 후 지우기

    # ---------- persistence ----------
    def _save(self):
        try:
            SAVE_FILE.write_text(json.dumps(self.commands, indent=2))
        except Exception as e:
            messagebox.showwarning("Warn", f"Could not save list: {e}")

    def _load(self):
        if not SAVE_FILE.exists():
            return
        try:
            self.commands = json.loads(SAVE_FILE.read_text())
            for name, cmd in self.commands:
                self._make_button(name, cmd)
        except Exception as e:
            messagebox.showwarning("Warn", f"Could not read list: {e}")


if __name__ == "__main__":
    CmdPad().mainloop()