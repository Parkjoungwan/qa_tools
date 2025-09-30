import tkinter as tk

class ToggleApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Toggle Switch")
        self.master.geometry("200x100")
        self.is_on = True  # 초기 상태

        self.toggle_button = tk.Button(
            self.master, text="re", width=10,
            bg="lightgreen", fg="black",
            command=self.toggle
        )
        self.toggle_button.pack(expand=True)

    def toggle(self):
        self.is_on = not self.is_on
        if self.is_on:
            self.toggle_button.config(text="re", bg="lightgreen")
        else:
            self.toggle_button.config(text="bone", bg="lightcoral")

if __name__ == "__main__":
    root = tk.Tk()
    app = ToggleApp(root)
    root.mainloop()

