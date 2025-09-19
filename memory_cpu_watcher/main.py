import tkinter as tk
from tkinter import messagebox
import subprocess
import re
import sys
import threading
import time
from collections import deque

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class AdbMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Android App Monitor")
        self.root.geometry("400x220") # Increased height for the button
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.running = True

        # --- Data Logging ---
        self.log_size = 15 # 30 seconds / 2 seconds interval
        self.cpu_log = deque(maxlen=self.log_size)
        self.mem_log = deque(maxlen=self.log_size)

        # --- GUI Elements ---
        self.app_name_label = tk.Label(self.root, text="App: N/A", font=("Helvetica", 12))
        self.app_name_label.pack(pady=5)
        self.cpu_label = tk.Label(self.root, text="CPU (Normalized): - %", font=("Helvetica", 12))
        self.cpu_label.pack(pady=5)
        self.mem_label = tk.Label(self.root, text="Memory: - MB", font=("Helvetica", 12))
        self.mem_label.pack(pady=5)
        self.mem_percent_label = tk.Label(self.root, text="Memory (vs Total): - %", font=("Helvetica", 12))
        self.mem_percent_label.pack(pady=5)
        
        self.diagram_button = tk.Button(self.root, text="Make Diagram", command=self.create_diagram)
        self.diagram_button.pack(pady=10)

        self.status_label = tk.Label(self.root, text="Initializing...", font=("Helvetica", 10), fg="blue")
        self.status_label.pack(side="bottom", fill="x")

        # --- Initial Checks ---
        self.total_mem_mb = 0
        self.cpu_core_count = 0
        self.device_ok = self._initial_checks()

        if self.device_ok:
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()
        else:
            self.status_label.config(text="ADB device not found or failed to get info.", fg="red")

    def _initial_checks(self):
        if not self._is_adb_device_connected(): messagebox.showerror("Error", "ADB device not found."); return False
        self.total_mem_mb = self._get_total_memory()
        if self.total_mem_mb == 0: messagebox.showerror("Error", "Failed to get total memory."); return False
        self.cpu_core_count = self._get_cpu_core_count()
        if self.cpu_core_count == 0: messagebox.showerror("Error", "Failed to get CPU core count."); return False
        return True

    def _run_adb_command(self, command):
        try:
            use_shell = sys.platform == "win32"
            cmd_str = f"adb {command}"
            cmd_arg = cmd_str.split() if not use_shell else cmd_str
            result = subprocess.run(cmd_arg, shell=use_shell, capture_output=True, text=True, check=True, encoding='utf-8')
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError): return None

    def _is_adb_device_connected(self):
        output = self._run_adb_command("devices")
        return output and len(output.splitlines()) > 1 and "device" in output

    def _get_total_memory(self):
        output = self._run_adb_command("shell cat /proc/meminfo")
        if output and (match := re.search(r"MemTotal:\s+(\d+)\s+kB", output)): return int(match.group(1)) / 1024
        return 0

    def _get_cpu_core_count(self):
        output = self._run_adb_command("shell top -n 1")
        if output and (match := re.search(r"(\d+)%cpu", output)): return int(match.group(1)) / 100
        return 0

    def _get_frontmost_package(self):
        output = self._run_adb_command("shell dumpsys window | grep mCurrentFocus")
        if output and (match := re.search(r"\s([^/\s]+)/", output)): return match.group(1)
        return None

    def _get_usage_stats(self, package_name):
        mem_mb, pid, cpu_percent_raw = 0, None, 0.0
        mem_output = self._run_adb_command(f"shell dumpsys meminfo {package_name}")
        if mem_output:
            if (pid_match := re.search(r"pid\s+(\d+)", mem_output)): pid = pid_match.group(1)
            if (mem_match := re.search(r"TOTAL\s+([\d,]+)", mem_output)): mem_mb = int(mem_match.group(1).replace(',', '')) / 1024
        if pid:
            top_output = self._run_adb_command(f"shell top -n 1 -p {pid}")
            if top_output:
                for line in top_output.splitlines():
                    if line.strip().startswith(pid):
                        try:
                            parts = line.strip().split()
                            if len(parts) >= 9: cpu_percent_raw = float(parts[8]); break
                        except (ValueError, IndexError): continue
        return cpu_percent_raw, mem_mb

    def _update_loop(self):
        while self.running:
            package = self._get_frontmost_package()
            if package:
                self.status_label.config(text=f"Monitoring: {package}", fg="green")
                cpu_raw, mem = self._get_usage_stats(package)
                
                cpu_normalized = (cpu_raw / self.cpu_core_count) if self.cpu_core_count > 0 else 0
                mem_perc = (mem / self.total_mem_mb) * 100 if self.total_mem_mb > 0 else 0
                
                self.cpu_log.append(cpu_normalized)
                self.mem_log.append(mem_perc)

                self.app_name_label.config(text=f"App: {package}")
                self.cpu_label.config(text=f"CPU (Normalized): {cpu_normalized:.2f} %")
                self.mem_label.config(text=f"Memory: {mem:.2f} MB")
                self.mem_percent_label.config(text=f"Memory (vs Total): {mem_perc:.2f} %")
            else:
                self.status_label.config(text="No focused app found.", fg="orange")
            time.sleep(2)

    def create_diagram(self):
        if len(self.cpu_log) < 2:
            messagebox.showinfo("Not Enough Data", "Please wait for at least a few seconds to collect more data.")
            return

        diagram_window = tk.Toplevel(self.root)
        diagram_window.title("Usage Diagram (Last 30s)")
        diagram_window.geometry("800x600")

        fig = Figure(figsize=(8, 6), dpi=100)
        ax1 = fig.add_subplot(2, 1, 1)
        ax2 = fig.add_subplot(2, 1, 2)

        # X-axis representing seconds from the start of logging
        x_axis = range(0, len(self.cpu_log) * 2, 2)

        ax1.plot(x_axis, list(self.cpu_log), marker='o', color='b')
        ax1.set_title('CPU Usage (%)')
        ax1.set_ylabel('CPU %')
        ax1.grid(True)

        ax2.plot(x_axis, list(self.mem_log), marker='o', color='r')
        ax2.set_title('Memory Usage (%)')
        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Memory %')
        ax2.grid(True)

        fig.tight_layout(pad=3.0)

        canvas = FigureCanvasTkAgg(fig, master=diagram_window)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)

    def _on_closing(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = AdbMonitor()
    app.run()