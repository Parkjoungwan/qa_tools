#!/usr/bin/env python3
import json, subprocess, shlex, tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Menu
from pathlib import Path
import threading
import os
import sys
import shutil



class CmdPad(tk.Tk):
    ROW_VISIBLE = 5
    BTN_HEIGHT = 40

    def __init__(self):
        super().__init__()
        self.title("Command Pad")
        self.data: dict[str, dict] = {}
        self.sheet_widgets: dict[str, dict] = {}
        self.current_proc: subprocess.Popen | None = None
        self._build_ui()
        self._load()

    # ---------- UI BUILD ----------
    def _build_ui(self):
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill="both", padx=5, pady=5)
        self.notebook.bind("<Button-3>", self._show_sheet_context_menu)

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=10, pady=(0, 10))

        add_cmd_btn = ttk.Button(bottom_frame, text="＋", width=3, command=self._add_cmd)
        add_cmd_btn.pack(side="right", padx=(5, 0))
        delete_cmd_btn = ttk.Button(bottom_frame, text="－", width=3, command=self._delete_cmd_dialog)
        delete_cmd_btn.pack(side="right", padx=(5, 0))
        reorder_cmd_btn = ttk.Button(bottom_frame, text="⇅", width=3, command=self._reorder_cmd_dialog)
        reorder_cmd_btn.pack(side="right", padx=(5, 0))

        add_sheet_btn = ttk.Button(bottom_frame, text="Add Sheet", command=self._add_sheet)
        add_sheet_btn.pack(side="left")

        self.status = ttk.Label(self, text="", anchor="w")
        self.status.pack(side="bottom", fill="x", padx=10, pady=(0, 8))

    def _create_sheet_ui(self, sheet_name: str) -> dict:
        sheet_frame = ttk.Frame(self.notebook)
        self.notebook.add(sheet_frame, text=sheet_name)

        canvas = tk.Canvas(sheet_frame, height=self.ROW_VISIBLE * self.BTN_HEIGHT + 8, highlightthickness=0)
        vsb = ttk.Scrollbar(sheet_frame, orient="vertical", command=canvas.yview)
        inner_frame = ttk.Frame(canvas)
        inner_frame.columnconfigure(0, weight=1)

        window_id = canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _on_configure(event):
            canvas.itemconfig(window_id, width=event.width)

        inner_frame.bind("<Configure>", _on_configure)

        # This handler will be passed to child widgets
        def _on_mousewheel(event):
            # Platform-specific scroll handling
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-1, "units")

        # Bind scrolling to the main scrollable areas
        canvas.bind("<MouseWheel>", _on_mousewheel)
        inner_frame.bind("<MouseWheel>", _on_mousewheel)

        return {"frame": sheet_frame, "canvas": canvas, "inner": inner_frame, "buttons": [], "scroll_handler": _on_mousewheel}

    def _make_button(self, sheet_name: str, cmd_obj: dict):
        sheet_ui = self.sheet_widgets[sheet_name]
        row_index = len(sheet_ui["buttons"])

        # 내부 프레임의 첫 번째 컬럼이 확장 가능하도록 설정
        sheet_ui["inner"].grid_columnconfigure(0, weight=1)

        # 버튼 생성
        btn = ttk.Button(
            sheet_ui["inner"],
            text=cmd_obj["name"],
            command=lambda c=cmd_obj: self._run(c)
        )
        # sticky="ew"로 가로 전체 확장, padx/pady는 여백
        btn.grid(row=row_index, column=0, sticky="ew", padx=5, pady=4)

        # 버튼 레퍼런스 보관 (상태 토글 & 나중에 destroy 위해 필요)
        sheet_ui["buttons"].append(btn)

        # 마우스 휠 스크롤도 버튼 위에서 작동하도록 연결
        scroll_handler = sheet_ui.get("scroll_handler")
        if scroll_handler:
            btn.bind("<MouseWheel>", scroll_handler)

    # ---------- SHEETS & CONFIG ----------
    def _add_sheet(self):
        sheet_name = simpledialog.askstring("New Sheet", "Enter sheet name:")
        if sheet_name and sheet_name not in self.data:
            self.data[sheet_name] = {
                "config": {"PKG": "com.example.app", "DEVICE1": "SERIAL1", "DEVICE2": "SERIAL2"},
                "commands": []
            }
            self.sheet_widgets[sheet_name] = self._create_sheet_ui(sheet_name)
            self.notebook.select(self.sheet_widgets[sheet_name]["frame"])
            self._save()
        elif sheet_name:
            messagebox.showwarning("Exists", f"Sheet '{sheet_name}' already exists.")

    def _show_sheet_context_menu(self, event):
        try:
            if "label" in self.notebook.identify(event.x, event.y):
                sheet_name = self.notebook.tab(self.notebook.select(), "text")
                context_menu = Menu(self, tearoff=0)
                context_menu.add_command(label="Edit Config", command=lambda: self._edit_config(sheet_name))
                context_menu.add_command(label=f"Delete '{sheet_name}' Sheet", command=lambda: self._delete_sheet(sheet_name))
                context_menu.post(event.x_root, event.y_root)
        except tk.TclError: pass

    def _edit_config(self, sheet_name):
        config = self.data[sheet_name].get("config", {})
        new_config_str = simpledialog.askstring("Edit Config", f"Editing config for {sheet_name}:", initialvalue=json.dumps(config, indent=2))
        if new_config_str:
            try:
                new_config = json.loads(new_config_str)
                self.data[sheet_name]["config"] = new_config
                self._save()
                messagebox.showinfo("Success", "Config updated successfully.")
            except json.JSONDecodeError:
                messagebox.showerror("Error", "Invalid JSON format.")

    def _delete_sheet(self, sheet_name):
        if messagebox.askyesno("Delete Sheet", f"Are you sure you want to delete '{sheet_name}'?"):
            self.notebook.forget(self.sheet_widgets[sheet_name]["frame"])
            del self.data[sheet_name]
            del self.sheet_widgets[sheet_name]
            self._save()

    def get_active_sheet_name(self) -> str | None: 
        try: return self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError: return None

    # ---------- COMMAND MANAGEMENT ----------
    def _refresh_sheet(self, sheet_name):
        sheet_ui = self.sheet_widgets.get(sheet_name)
        if not sheet_ui: return
        for btn in sheet_ui["buttons"]:
            btn.destroy()
        sheet_ui["buttons"].clear()
        for cmd_obj in self.data[sheet_name].get("commands", []):
            self._make_button(sheet_name, cmd_obj)
        sheet_ui["canvas"].update_idletasks()
        sheet_ui["canvas"].config(scrollregion=sheet_ui["canvas"].bbox("all"))

    def _add_cmd(self):
        active_sheet = self.get_active_sheet_name()
        if not active_sheet: return
        name = simpledialog.askstring("Name", "Button name:")
        if not name: return
        script = simpledialog.askstring("Script", "Script name (e.g., rebootApp.sh):")
        if not script: return
        args = simpledialog.askstring("Args", "Arguments (e.g., 1 2):", initialvalue="1")
        new_cmd = {"name": name, "script": script, "args": args or ""}
        self.data[active_sheet]["commands"].append(new_cmd)
        self._refresh_sheet(active_sheet)
        self._save()

    def _delete_cmd_dialog(self):
        messagebox.showinfo("Info", "This feature is under development. Please edit cmd_pad.json directly.")

    def _reorder_cmd_dialog(self):
        messagebox.showinfo("Info", "This feature is under development. Please edit cmd_pad.json directly.")

    # ---------- RUN / MONITOR ----------
    def _run(self, cmd_obj: dict):
        if self.current_proc and self.current_proc.poll() is None: messagebox.showwarning("Busy", "Another command is running."); return

        sheet_name = self.get_active_sheet_name()
        if not sheet_name: return

        config = self.data[sheet_name].get("config", {})
        env = os.environ.copy()
        
        global_config = self.data.get("global_config", {})
        adb_path = global_config.get("ADB_PATH")
        if adb_path and Path(adb_path).exists():
            env["PATH"] = f"{Path(adb_path).parent}{os.pathsep}{env.get('PATH', '')}"

        env.update(config)

        script_path = SCRIPTS_DIR / cmd_obj["script"]
        if not script_path.exists():
            messagebox.showerror("Error", f"Script not found: {script_path}")
            return

        command_line = ["sh", str(script_path)] + shlex.split(cmd_obj.get("args", ""))
        
        for sheet_ui in self.sheet_widgets.values():
            for btn in sheet_ui["buttons"]:
                btn.state(["disabled"])
        self.status.config(text=f"▶ '{cmd_obj['name']}' running…")

        thread = threading.Thread(target=self._execute_command_in_thread, args=(cmd_obj, command_line, env), daemon=True)
        thread.start()

    def _execute_command_in_thread(self, cmd_obj: dict, command_line: list, env: dict):
        try:
            self.current_proc = subprocess.Popen(command_line, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', env=env)
            stdout, stderr = self.current_proc.communicate()
            self.after(0, self._on_command_finish, cmd_obj, self.current_proc.returncode, stdout, stderr)
        except Exception as e:
            self.after(0, self._on_command_error, str(e))
        finally:
            self.current_proc = None

    def _on_command_finish(self, cmd_obj: dict, return_code: int, stdout: str, stderr: str):
        for sheet_ui in self.sheet_widgets.values():
            for btn in sheet_ui["buttons"]:
                btn.state(["!disabled"])
        output_msg = f"'{cmd_obj['name']}' finished (code: {return_code})"
        self.status.config(text=output_msg)
        if stdout or stderr:
            details = f'''Stdout:\n{stdout}\n\nStderr:\n{stderr}'''
            messagebox.showinfo(f"'{cmd_obj['name']}' Output", details)
        self.after(5000, lambda: self.status.config(text=""))

    def _on_command_error(self, error_message: str):
        for sheet_ui in self.sheet_widgets.values():
            for btn in sheet_ui["buttons"]:
                btn.state(["!disabled"])
        self.status.config(text=f"Error: {error_message}")
        messagebox.showerror("Error", error_message)

    # ---------- PERSISTENCE ----------
    def _save(self):
        try: SAVE_FILE.write_text(json.dumps(self.data, indent=2, ensure_ascii=False))
        except Exception as e: messagebox.showwarning("Warn", f"Could not save: {e}")

    def _load(self):
        # Set base directory for bundled app support
        if getattr(sys, 'frozen', False):
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        
        global SAVE_FILE, SCRIPTS_DIR
        SAVE_FILE = base_dir / "cmd_pad.json"
        SCRIPTS_DIR = base_dir / "scripts"

        if not SAVE_FILE.exists():
            self.data = {}
            self._add_sheet()
            return
        try:
            self.data = json.loads(SAVE_FILE.read_text())
            if not self.data:
                self._add_sheet()
                return
            for sheet_name in self.data:
                self.sheet_widgets[sheet_name] = self._create_sheet_ui(sheet_name)
                self._refresh_sheet(sheet_name)
        except Exception as e: 
            messagebox.showwarning("Warn", f"Could not read data: {e}")
            self.data = {}
            self._add_sheet()

if __name__ == "__main__":
    CmdPad().mainloop()
