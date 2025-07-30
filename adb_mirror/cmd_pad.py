#!/usr/bin/env python3
# cmd_buttons.py  –  macOS-friendly Tk GUI

import json, subprocess, shlex, tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from pathlib import Path

SAVE_FILE = Path(__file__).with_suffix(".json")   # 버튼 목록 저장용

class CmdPad(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Command Pad")
        self.commands: list[tuple[str,str]] = []
        self._build_ui()
        self._load()

    # ---------- UI ----------
    def _build_ui(self):
        self.btn_frame = ttk.Frame(self, padding=10)
        self.btn_frame.grid(row=0, column=0, sticky="nsew")

        add_btn = ttk.Button(self, text="＋", width=3, command=self._add_cmd)
        add_btn.grid(row=1, column=0, sticky="e", padx=10, pady=(0,10))

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    # ---------- command ops ----------
    def _add_cmd(self):
        name = simpledialog.askstring("Name", "Button name:")
        if not name:
            return
        cmd  = simpledialog.askstring("Command", f"Shell command for '{name}':")
        if not cmd:
            return

        self.commands.append((name, cmd))
        self._make_button(name, cmd)
        self._save()

    def _make_button(self, name: str, cmd: str):
        btn = ttk.Button(self.btn_frame, text=name,
                         command=lambda c=cmd: self._run(c))
        btn.pack(fill="x", pady=4)

    def _run(self, cmd: str):
        try:
            subprocess.Popen(shlex.split(cmd),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Command not found:\n{cmd}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------- persistence ----------
    def _save(self):
        try:
            SAVE_FILE.write_text(json.dumps(self.commands, indent=2))
        except Exception as e:
            messagebox.showwarning("Warn", f"Could not save list:\n{e}")

    def _load(self):
        if not SAVE_FILE.exists():
            return
        try:
            self.commands = json.loads(SAVE_FILE.read_text())
            for name, cmd in self.commands:
                self._make_button(name, cmd)
        except Exception as e:
            messagebox.showwarning("Warn", f"Could not read list:\n{e}")

if __name__ == "__main__":
    CmdPad().mainloop()

