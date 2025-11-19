import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import *
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from PIL import Image, ImageTk
import os, time, json, subprocess

# =========================
# PATHS
# =========================
VIDEO_PATH = "/home/neonflake/packproof/videos"
IMAGE_PATH = "/home/neonflake/packproof/images"
LOG_FILE   = "/home/neonflake/packproof/upload_log.json"
WIFI_PY    = "/home/neonflake/codes/wifi.py"

os.makedirs(VIDEO_PATH, exist_ok=True)
os.makedirs(IMAGE_PATH, exist_ok=True)

# =========================
# UI CONSTANTS
# =========================
BTN_FONT_FAMILY = "Arial"
BTN_FONT_SIZE   = 56
TITLE_FONT      = ("Arial", 54, "bold")
ENTRY_FONT      = ("Arial", 48)
ENTRY_IPADY     = 32

# =========================
# QUEUE HANDLER
# =========================
def add_to_upload_queue(order_id: str):
    data = {"pending": [], "uploaded": []}
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except:
            pass
    if not any(e.get("id") == order_id for e in data["pending"]):
        data["pending"].append({"id": order_id})
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[Queue] Added: {order_id}")

# =========================
# NUMERIC KEYPAD (full-screen)
# =========================
class NumericKeypad(tk.Toplevel):
    def __init__(self, master, target_entry, on_close_cb=None):
        super().__init__(master)
        self.target = target_entry
        self.on_close_cb = on_close_cb

        self.overrideredirect(True)
        self.configure(bg="white")
        # full-screen on typical 1280x720 layout used earlier
        # if your display is different, this still covers the root window
        self.geometry("1280x720+0+0")
        # ensure focus so clicks go to this window
        self.after(50, lambda: self.grab_set())

        root = tk.Frame(self, bg="white")
        root.place(relx=0, rely=0, relwidth=1, relheight=1)

        # grid layout
        for i in range(3):
            root.columnconfigure(i, weight=1)
        for i in range(6):
            root.rowconfigure(i, weight=1)

        self.var = tk.StringVar(value=self.target.get())

        entry = tk.Entry(root, textvariable=self.var,
                         font=("Arial", 36), justify="center",
                         relief="solid", bd=4)
        entry.grid(row=0, column=0, columnspan=3, sticky="nsew", pady=10, padx=12)

        def mk_btn(txt, cmd, r, c):
            b = tk.Button(root, text=txt, command=cmd,
                          font=("Arial", 40), bg="#2c3e50",
                          fg="white", relief="flat")
            b.grid(row=r, column=c, padx=16, pady=12, sticky="nsew")

        nums = ["1","2","3","4","5","6","7","8","9"]
        idx = 0
        for r in range(1,4):
            for c in range(3):
                mk_btn(nums[idx], lambda x=nums[idx]: self.add_digit(x), r, c)
                idx += 1

        mk_btn("DEL", self.backspace, 4, 0)
        mk_btn("0", lambda: self.add_digit("0"), 4, 1)
        mk_btn("CLR", self.clear_all, 4, 2)

        bottom = tk.Frame(root, bg="white")
        bottom.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=8, padx=12)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        ok = tk.Button(bottom, text="OK",
                       font=("Arial", 40, "bold"),
                       bg="#1f8a50", fg="white", relief="flat",
                       command=self.finish)
        ok.grid(row=0, column=0, padx=18, pady=10, sticky="nsew")

        back = tk.Button(bottom, text="BACK",
                         font=("Arial", 40, "bold"),
                         bg="#8a2b2b", fg="white", relief="flat",
                         command=self.close_only)
        back.grid(row=0, column=1, padx=18, pady=10, sticky="nsew")

    def add_digit(self, d): self.var.set(self.var.get() + d)
    def backspace(self): self.var.set(self.var.get()[:-1])
    def clear_all(self): self.var.set("")

    def finish(self):
        self.target.delete(0, tk.END)
        self.target.insert(0, self.var.get())
        self.close_only()

    def close_only(self):
        try:
            self.grab_release()
        except:
            pass
        self.destroy()
        if self.on_close_cb:
            # notify parent that keypad closed
            try:
                self.on_close_cb()
            except:
                pass

# =========================
# MAIN APP
# =========================
class RecorderApp:
    def __init__(self, master):
        self.master = master
        master.configure(bg="white")
        master.bind("<Escape>", lambda e: master.destroy())

        # style for start button (ttkbootstrap)
        self.style = ttkbs.Style()
        self.style.configure(
            "Start.TButton",
            font=(BTN_FONT_FAMILY, BTN_FONT_SIZE, "bold"),
            background="#FF8C00",
            foreground="black",
            padding=(30, 50),
            borderwidth=0
        )
        self.style.map("Start.TButton",
                       background=[("active", "#FF8C00"),
                                   ("pressed", "#FF8C00"),
                                   ("hover", "#FF8C00")])

        # camera setup (Picamera2)
        self.picam2 = Picamera2()
        self.preview_cfg = self.picam2.create_preview_configuration(main={"size": (640, 480)})
        self.video_cfg   = self.picam2.create_video_configuration(main={"size": (640, 480)})
        self.picam2.configure(self.preview_cfg)
        self.picam2.start()

        self.keypad_open = False
        self.preview_running = False

        self.build_home()

    # ---------- home screen ----------
    def build_home(self):
        # clear
        for w in self.master.winfo_children():
            w.destroy()

        # top bar with settings icon
        top = tk.Frame(self.master, bg="white")
        top.pack(fill="x", side="top")

        # bigger settings icon (emoji)
        tk.Button(
            top, text="⚙️", font=("Arial", 72, "bold"),
            bg="white", fg="black", relief="flat",
            command=self.open_settings
        ).pack(side="right", padx=40, pady=25)

        # main wrapper
        wrapper = tk.Frame(self.master, bg="white")
        wrapper.pack(fill="both", expand=True, padx=36, pady=26)

        tk.Label(wrapper, text="Enter Order ID", font=TITLE_FONT, bg="white").pack(pady=(8, 18))

        # thick black border frame (entry inside)
        border_frame = tk.Frame(wrapper, bg="black", bd=12, relief="solid")
        border_frame.pack(fill="x", pady=(6, 36))

        self.id_entry = tk.Entry(border_frame,
                                 font=ENTRY_FONT,
                                 justify="center",
                                 bg="white",
                                 fg="black",
                                 relief="flat")
        self.id_entry.pack(fill="x", ipady=ENTRY_IPADY, ipadx=18)

        # bind entry only (keypad appears only when tapping entry)
        self.id_entry.bind("<Button-1>", lambda e: self.open_keypad())

        # Start recording button (ttk bootstrap)
        ttkbs.Button(wrapper, text="START RECORDING",
                     style="Start.TButton", command=self.start_recording).pack(fill="x", pady=(20, 14))

    # ---------- keypad open/close ----------
    def open_keypad(self):
        if self.keypad_open:
            return
        self.keypad_open = True
        NumericKeypad(self.master, self.id_entry, on_close_cb=self._on_keypad_close)

    def _on_keypad_close(self):
        self.keypad_open = False

    # ---------- settings page ----------
    def open_settings(self):
        for w in self.master.winfo_children():
            w.destroy()

        wrap = tk.Frame(self.master, bg="white")
        wrap.pack(fill="both", expand=True, padx=8, pady=8)

        tk.Label(wrap, text="Settings", font=("Arial", 60, "bold"), bg="white").pack(pady=(18, 30))

        def big_btn(text, cmd):
            return tk.Button(wrap, text=text,
                              font=("Arial", 48, "bold"),
                              bg="#2c3e50", fg="white",
                              relief="flat", height=2, command=cmd)

        big_btn("ADJUST CAMERA ANGLE", self.show_preview).pack(fill="x", padx=28, pady=18)
        big_btn("WI-FI SETTINGS", self.open_wifi_settings).pack(fill="x", padx=28, pady=18)
        big_btn("BACK", self.build_home).pack(fill="x", padx=28, pady=18)

    def open_wifi_settings(self):
        # Launch the wifi.py file in a separate process so main UI continues
        try:
            subprocess.Popen(["python3", WIFI_PY])
        except Exception as e:
            print("Failed to open Wi-Fi UI:", e)

    # ---------- camera preview ----------
    def show_preview(self):
        for w in self.master.winfo_children():
            w.destroy()

        main = tk.Frame(self.master, bg="white")
        main.pack(fill="both", expand=True)

        self.preview_label = tk.Label(main, bg="white")
        self.preview_label.pack(expand=True, fill="both")

        tk.Button(main, text="BACK",
                  font=("Arial", 44, "bold"),
                  bg="#2c3e50", fg="white", relief="flat",
                  command=self.close_preview).pack(fill="x", pady=18, padx=24)

        self.preview_running = True
        self._update_preview_loop()

    def _update_preview_loop(self):
        if not self.preview_running:
            return
        try:
            frame = self.picam2.capture_array()
            img = ImageTk.PhotoImage(Image.fromarray(frame))
            self.preview_label.config(image=img)
            self.preview_label.image = img
        except Exception:
            pass
        # schedule next update
        self.master.after(120, self._update_preview_loop)

    def close_preview(self):
        self.preview_running = False
        self.build_home()

    # ---------- recording ----------
    def start_recording(self):
        order_id = self.id_entry.get().strip()
        if not order_id:
            self.alert("Empty", "Please enter Order ID")
            return

        outfile = os.path.join(VIDEO_PATH, f"{order_id}.mp4")
        if os.path.exists(outfile):
            try:
                os.remove(outfile)
            except:
                pass

        try:
            self.encoder = H264Encoder(bitrate=3_000_000)
            self.output = FfmpegOutput(outfile)
            self.picam2.switch_mode(self.video_cfg)
            time.sleep(0.3)
            self.picam2.start_recording(self.encoder, self.output)
        except Exception as e:
            print("Start recording failed:", e)
            self.alert("Error", "Failed to start recording.")
            # try to reset preview mode
            try:
                self.picam2.switch_mode(self.preview_cfg)
            except:
                pass
            return

        self.build_record_screen(order_id)

    def build_record_screen(self, oid):
        for w in self.master.winfo_children():
            w.destroy()

        wrap = tk.Frame(self.master, bg="white")
        wrap.pack(fill="both", expand=True, padx=32, pady=24)

        tk.Label(wrap, text=f"Recording: {oid}",
                 font=("Arial", 40, "bold"), bg="white").pack(pady=(8, 14))

        self.timer_lbl = tk.Label(wrap, text="(00:00)",
                                  font=("Arial", 40, "bold"), bg="white")
        self.timer_lbl.pack(pady=(8, 14))

        self.rec_start_time = time.time()
        self._update_timer()

        tk.Button(wrap, text="STOP RECORDING",
                  font=("Arial", 44, "bold"),
                  bg="#2c3e50", fg="white", relief="flat",
                  height=2, command=self.stop_recording).pack(fill="x", pady=18, padx=8)

        self.current_order = oid

    def _update_timer(self):
        try:
            elapsed = int(time.time() - self.rec_start_time)
            mm, ss = elapsed // 60, elapsed % 60
            self.timer_lbl.config(text=f"({mm:02d}:{ss:02d})")
        except Exception:
            pass
        self.master.after(1000, self._update_timer)

    def stop_recording(self):
        try:
            self.picam2.stop_recording()
        except Exception:
            pass

        try:
            add_to_upload_queue(self.current_order)
        except Exception:
            pass

        try:
            self.picam2.switch_mode(self.preview_cfg)
        except Exception:
            pass

        self.build_home()

    # ---------- alert dialog ----------
    def alert(self, title, message):
        win = tk.Toplevel(self.master)
        win.overrideredirect(True)
        win.geometry("900x420+200+150")
        win.configure(bg="white")

        tk.Label(win, text=title, font=("Arial", 60, "bold"), bg="white").pack(pady=20)
        tk.Label(win, text=message, font=("Arial", 36), bg="white", wraplength=800).pack(pady=10)

        tk.Button(win, text="OK", font=("Arial", 48),
                  bg="#2c3e50", fg="white", relief="flat",
                  command=win.destroy).pack(fill="x", pady=20)

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    root = ttkbs.Window(themename="flatly")
    # set fullscreen reliably
    root.after(50, lambda: root.attributes("-fullscreen", True))
    RecorderApp(root)
    root.mainloop()
