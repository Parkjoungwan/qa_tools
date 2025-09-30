import tkinter as tk
from datetime import datetime, timedelta

class CountdownApp:
    def __init__(self, master):
        self.master = master
        self.master.title("")
        self.master.geometry("300x100")
        self.master.configure(bg="black")

        self.label = tk.Label(
            master, text="", font=("Arial", 16),
            bg="black", fg="black"
        )
        self.label.pack(expand=True, fill="both")

        self.holding = False
        self.transition_start = 9  # 09:00
        self.transition_end = 18  # 18:00
        self.transition_duration = (self.transition_end - self.transition_start) * 3600  # 8시간 = 28800초

        master.bind("<ButtonPress-1>", self.start_hold)
        master.bind("<ButtonRelease-1>", self.end_hold)

    def start_hold(self, event):
        self.holding = True
        self.update_timer()

    def end_hold(self, event):
        self.holding = False
        self.label.config(text="", bg="black")

    def get_transition_ratio(self, now):
        """09시~18시 사이면 점점 밝아지는 비율 계산, 아니면 0"""
        start = now.replace(hour=self.transition_start, minute=0, second=0, microsecond=0)
        end = now.replace(hour=self.transition_end, minute=0, second=0, microsecond=0)

        if now < start:
            return 0  # 9시 전은 검정
        elif now > end:
            return 1  # 6시 이후면 완전 흰색
        else:
            elapsed = (now - start).total_seconds()
            return elapsed / self.transition_duration

    def brightness_color(self, ratio):
        level = int(255 * ratio)
        return f'#{level:02x}{level:02x}{level:02x}'

    def update_timer(self):
        if self.holding:
            now = datetime.now()
            target = now.replace(hour=18, minute=0, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)

            remaining = int((target - now).total_seconds())
            brightness_ratio = self.get_transition_ratio(now)
            bg_color = self.brightness_color(brightness_ratio)

            self.label.config(text=f"{remaining:,} 초 남음", bg=bg_color, fg="black")
            self.master.after(200, self.update_timer)

if __name__ == "__main__":
    root = tk.Tk()
    app = CountdownApp(root)
    root.mainloop()

