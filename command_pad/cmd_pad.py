#!/usr/bin/env python3
# cmd_buttons.py  – full-width buttons, scroll, process-aware status/lock

import json, subprocess, shlex, tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Menu # Menu import 추가
from pathlib import Path
import threading # threading 모듈 추가

SAVE_FILE = Path(__file__).parent / "cmd_pad.json"

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

        # 삭제 버튼 추가
        delete_btn = ttk.Button(self, text="－", width=3, command=self._delete_cmd_dialog)
        delete_btn.grid(row=1, column=0, sticky="w", padx=10, pady=(6, 10))

        # 재정렬 버튼 추가
        reorder_btn = ttk.Button(self, text="⇅", width=3, command=self._reorder_cmd_dialog)
        reorder_btn.grid(row=1, column=0, sticky="n", padx=10, pady=(6, 10))

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
        # 우클릭 이벤트 바인딩
        btn.bind("<Button-3>", lambda event, b=btn, n=name, c=cmd: self._show_context_menu(event, b, n, c))

    def _show_context_menu(self, event, button, name, cmd):
        context_menu = Menu(self, tearoff=0)
        context_menu.add_command(label="편집", command=lambda: self._edit_cmd(button, name, cmd)) # 편집 메뉴 추가
        context_menu.add_command(label="제거", command=lambda: self._remove_cmd(button, name, cmd))
        context_menu.post(event.x_root, event.y_root)

    def _edit_cmd(self, button, old_name, old_cmd):
        new_name = simpledialog.askstring("이름 편집", "새 버튼 이름:", initialvalue=old_name)
        if new_name is None: # 취소
            return
        new_cmd = simpledialog.askstring("명령어 편집", f"'{new_name}'에 대한 새 셸 명령어:", initialvalue=old_cmd)
        if new_cmd is None: # 취소
            return

        if new_name == old_name and new_cmd == old_cmd:
            messagebox.showinfo("정보", "변경 사항이 없습니다.")
            return

        # self.commands 리스트에서 기존 명령어 제거 후 새 명령어 추가
        # 인덱스를 찾아서 수정하는 것이 더 효율적이지만, 여기서는 간단하게 제거 후 추가
        try:
            idx = self.commands.index((old_name, old_cmd))
            self.commands[idx] = (new_name, new_cmd)
        except ValueError:
            # 만약 찾지 못하면 (예: 이미 삭제되었거나 변경되었을 경우)
            messagebox.showerror("오류", "명령어를 찾을 수 없습니다. 새로고침 후 다시 시도해주세요.")
            return

        # GUI 버튼 업데이트
        button.config(text=new_name) # 버튼 텍스트만 변경

        # 파일 저장
        self._save()
        self.status.config(text=f"'{old_name}' 명령어가 '{new_name}'으로 수정 완료")
        self.after(3000, lambda: self.status.config(text=""))

    def _delete_cmd_dialog(self):
        if not self.commands:
            messagebox.showinfo("정보", "삭제할 명령어가 없습니다.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("명령어 삭제")
        dialog.transient(self) # 부모 창 위에 표시
        dialog.grab_set()      # 다른 창 조작 방지

        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(padx=10, pady=10, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical")
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, selectmode="single")
        scrollbar.config(command=listbox.yview)

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for name, _ in self.commands:
            listbox.insert(tk.END, name)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=5)

        delete_btn = ttk.Button(button_frame, text="삭제", command=lambda: self._perform_delete(listbox, dialog))
        delete_btn.pack(side="left", padx=5)

        cancel_btn = ttk.Button(button_frame, text="취소", command=dialog.destroy)
        cancel_btn.pack(side="left", padx=5)

        self.wait_window(dialog) # 팝업 창이 닫힐 때까지 대기

    def _perform_delete(self, listbox, dialog):
        selected_indices = listbox.curselection()
        if not selected_indices:
            messagebox.showinfo("정보", "삭제할 명령어를 선택해주세요.")
            return

        idx_to_delete = selected_indices[0]
        name_to_delete, cmd_to_delete = self.commands[idx_to_delete]

        if messagebox.askyesno("확인", f"'{name_to_delete}' 명령어를 정말 삭제하시겠습니까?"):
            # self.commands 리스트에서 제거
            self.commands.pop(idx_to_delete)

            # GUI에서 버튼 제거 (기존 버튼 위젯을 찾아서 제거)
            # 이 부분은 self.btn_widgets 리스트와 self.commands 리스트의 동기화가 필요
            # 가장 간단한 방법은 모든 버튼을 다시 그리는 것
            for btn in self.btn_widgets:
                btn.destroy()
            self.btn_widgets.clear()
            for name, cmd in self.commands:
                self._make_button(name, cmd)

            # 파일 저장
            self._save()
            self.status.config(text=f"'{name_to_delete}' 명령어 제거 완료")
            self.after(3000, lambda: self.status.config(text=""))
            dialog.destroy()
        else:
            dialog.destroy()

    def _reorder_cmd_dialog(self):
        if not self.commands:
            messagebox.showinfo("정보", "재정렬할 명령어가 없습니다.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("명령어 재정렬")
        dialog.transient(self)
        dialog.grab_set()

        listbox_frame = ttk.Frame(dialog)
        listbox_frame.pack(padx=10, pady=10, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical")
        listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, selectmode="single")
        scrollbar.config(command=listbox.yview)

        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for name, _ in self.commands:
            listbox.insert(tk.END, name)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=5)

        up_btn = ttk.Button(button_frame, text="위로 이동", command=lambda: self._move_cmd(listbox, -1))
        up_btn.pack(side="left", padx=5)

        down_btn = ttk.Button(button_frame, text="아래로 이동", command=lambda: self._move_cmd(listbox, 1))
        down_btn.pack(side="left", padx=5)

        ok_btn = ttk.Button(button_frame, text="확인", command=dialog.destroy)
        ok_btn.pack(side="left", padx=5)

        self.wait_window(dialog)

    def _move_cmd(self, listbox, direction):
        selected_indices = listbox.curselection()
        if not selected_indices:
            return

        idx = selected_indices[0]
        new_idx = idx + direction

        if 0 <= new_idx < len(self.commands):
            # self.commands 리스트에서 순서 변경
            self.commands[idx], self.commands[new_idx] = self.commands[new_idx], self.commands[idx]

            # GUI 버튼 다시 그리기
            for btn in self.btn_widgets:
                btn.destroy()
            self.btn_widgets.clear()
            for name, cmd in self.commands:
                self._make_button(name, cmd)

            # Listbox 업데이트 및 선택 유지
            listbox.delete(0, tk.END)
            for name, _ in self.commands:
                listbox.insert(tk.END, name)
            listbox.selection_set(new_idx)
            listbox.see(new_idx)

            self._save()

            # Update canvas scroll region after moving command
            self.canvas.update_idletasks()
            self.canvas.config(scrollregion=self.canvas.bbox("all"))

    # ---------- run / monitor ----------
    def _run(self, name: str, cmd: str):
        if self.current_proc and self.current_proc.poll() is None:
            messagebox.showwarning("실행 중", "이미 다른 명령어가 실행 중입니다.")
            return

        for btn in self.btn_widgets:
            btn.state(["disabled"])
        self.status.config(text=f"▶ '{name}' 실행 중…")

        thread = threading.Thread(target=self._execute_command_in_thread,
                                  args=(name, cmd), daemon=True)
        thread.start()

    def _execute_command_in_thread(self, name: str, cmd: str):
        try:
            self.current_proc = subprocess.Popen(
                shlex.split(cmd),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            stdout, stderr = self.current_proc.communicate()
            return_code = self.current_proc.returncode
            self.after(0, self._on_command_finish, name, return_code, stdout, stderr)
        except FileNotFoundError:
            self.after(0, self._on_command_error, f"명령어를 찾을 수 없습니다: {cmd}")
        except Exception as e:
            self.after(0, self._on_command_error, str(e))
        finally:
            self.current_proc = None

    def _on_command_finish(self, name: str, return_code: int, stdout: str, stderr: str):
        for btn in self.btn_widgets:
            btn.state(["!disabled"])

        output_msg = f"'{name}' 실행 완료 (코드: {return_code})\n"
        if stdout:
            output_msg += f"Stdout:\n{stdout}\n"
        if stderr:
            output_msg += f"Stderr:\n{stderr}\n"
        self.status.config(text=output_msg)
        self.after(5000, lambda: self.status.config(text=""))

    def _on_command_error(self, error_message: str):
        for btn in self.btn_widgets:
            btn.state(["!disabled"])
        self.status.config(text=f"오류: {error_message}")
        messagebox.showerror("오류", error_message)
        self.after(5000, lambda: self.status.config(text=""))

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
