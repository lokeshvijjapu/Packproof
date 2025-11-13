import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import *
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FfmpegOutput
from PIL import Image, ImageTk
import os, time, json

# =========================
# PATHS
# =========================
VIDEO_PATH = "/home/neonflake/packproof/videos"
IMAGE_PATH = "/home/neonflake/packproof/images"
LOG_FILE   = "/home/neonflake/packproof/upload_log.json"
os.makedirs(VIDEO_PATH, exist_ok=True)
os.makedirs(IMAGE_PATH, exist_ok=True)

# =========================
# UI CONSTANTS
# =========================
BTN_FONT_FAMILY = "Arial"
BTN_FONT_SIZE   = 56
BTN_PAD_Y       = 44
BTN_PAD_X       = 28
TITLE_FONT      = ("Arial", 54, "bold")
ENTRY_FONT      = ("Arial", 52)
ENTRY_IPADY     = 28

PREVIEW_MARGIN_W = 200
PREVIEW_MARGIN_H = 240

# =========================
# QUEUE HANDLER
# =========================
def add_to_upload_queue(invoice_id: str):
    data = {"pending": [], "uploaded": []}
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                data = json.load(f)
        except:
            pass
    if not any(e.get("id") == invoice_id for e in data["pending"]):
        data["pending"].append({"id": invoice_id})
        with open(LOG_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"ðŸ“¦ Added {invoice_id} to upload queue")

# =========================
# NUMERIC KEYPAD
# =========================
class NumericKeypad(tk.Toplevel):
    def __init__(self, master, target_entry: ttk.Entry, on_close_cb=None):
        super().__init__(master)
        self.target = target_entry
        self.on_close_cb = on_close_cb

        self.overrideredirect(True)
        self.configure(bg="white")
        self.geometry("1280x720+0+0")
        self.after(50, lambda: self.grab_set())

        root_frame = ttk.Frame(self, padding=10)
        root_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        for i in range(3):
            root_frame.columnconfigure(i, weight=1)
        for i in range(6):
            root_frame.rowconfigure(i, weight=1)

        self.var = tk.StringVar(value=self.target.get())

        entry = ttk.Entry(root_frame, textvariable=self.var,
                          font=("Arial", 36), width=16, justify="center")
        entry.grid(row=0, column=0, columnspan=3, pady=(0, 18), sticky="nsew")

        def mk_btn(txt, cmd, r, c):
            b = tk.Button(root_frame, text=txt, command=cmd,
                          font=("Arial", 36),
                          bg="#2c3e50", fg="white",
                          relief="flat")
            b.grid(row=r, column=c, padx=16, pady=10, ipadx=12, ipady=12, sticky="nsew")

        nums = ["1","2","3","4","5","6","7","8","9"]
        k = 0
        for r in range(1,4):
            for c in range(3):
                mk_btn(nums[k], lambda x=nums[k]: self.add_digit(x), r, c)
                k += 1

        mk_btn("DEL", self.backspace, 4, 0)
        mk_btn("0",   lambda: self.add_digit("0"), 4, 1)
        mk_btn("CLR", self.clear_all, 4, 2)

        bottom = ttk.Frame(root_frame)
        bottom.grid(row=5, column=0, columnspan=3, pady=(12, 0), sticky="nsew")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)

        ok = tk.Button(bottom, text="OK",
                       font=("Arial", 34, "bold"),
                       bg="#1f8a50", fg="white", relief="flat",
                       command=self.finish)
        ok.grid(row=0, column=0, padx=24, pady=10, ipady=18, sticky="nsew")

        back = tk.Button(bottom, text="BACK",
                         font=("Arial", 34, "bold"),
                         bg="#8a2b2b", fg="white", relief="flat",
                         command=self.close_only)
        back.grid(row=0, column=1, padx=24, pady=10, ipady=18, sticky="nsew")

    def add_digit(self, d): self.var.set(self.var.get() + d)
    def backspace(self):   self.var.set(self.var.get()[:-1])
    def clear_all(self):   self.var.set("")
    def finish(self):
        self.target.delete(0, tk.END)
        self.target.insert(0, self.var.get())
        self.close_only()
    def close_only(self):
        try: self.grab_release()
        except: pass
        self.destroy()
        if self.on_close_cb:
            self.on_close_cb()

# =========================
# MAIN APP
# =========================
class RecorderApp:
    def __init__(self, master):
        self.master = master

        master.overrideredirect(True)
        master.attributes("-fullscreen", True)

        master.configure(bg="white")
        master.bind("<Escape>", lambda e: master.destroy())

        self.big_font = (BTN_FONT_FAMILY, BTN_FONT_SIZE, "bold")

        # ====================================
        # CUSTOM ORANGE STYLE FOR START BUTTON
        # ====================================
        self.style = ttkbs.Style()
        self.style.configure(
            "Start.TButton",
            font=self.big_font,
            background="#FF8C00",
            foreground="black"
        )

        self.picam2 = Picamera2()
        self.preview_cfg = self.picam2.create_preview_configuration(main={"size": (640, 480)})
        self.video_cfg   = self.picam2.create_video_configuration(main={"size": (640, 480)})
        self.picam2.configure(self.preview_cfg)
        self.picam2.start()

        self.preview_running = False
        self.invoice_id = ""
        self.keypad_open = False

        self.build_page1()

    def big_button(self, parent, text, command):
        return tk.Button(
            parent, text=text, font=self.big_font,
            bg="#2c3e50", fg="white",
            relief="flat",
            command=command
        )

    def build_page1(self):
        for w in self.master.winfo_children():
            w.destroy()

        wrapper = ttk.Frame(self.master, padding=40)
        wrapper.pack(fill="both", expand=True)

        ttk.Label(wrapper, text="Enter Invoice ID", font=TITLE_FONT).pack(pady=(16, 12))

        self.id_entry = ttk.Entry(wrapper, font=ENTRY_FONT, width=18, justify="center")
        self.id_entry.pack(pady=(10, 36), ipady=ENTRY_IPADY)
        self.id_entry.bind("<Button-1>", lambda e: self.open_keypad())

        btn_wrap = ttk.Frame(wrapper)
        btn_wrap.pack(fill="both", expand=True)

        btn_wrap.rowconfigure(0, weight=1)
        btn_wrap.rowconfigure(1, weight=1)
        btn_wrap.columnconfigure(0, weight=1)

        show_btn = self.big_button(btn_wrap, "SHOW PREVIEW", self.show_preview_overlay)
        show_btn.grid(row=0, column=0, padx=BTN_PAD_X, pady=BTN_PAD_X, sticky="nsew")

        # =========== ORANGE START BUTTON ===========
        start_btn = ttkbs.Button(
            btn_wrap,
            text="START RECORDING",
            style="Start.TButton",
            command=self.start_recording
        )
        start_btn.grid(row=1, column=0, padx=BTN_PAD_X, pady=BTN_PAD_X, sticky="nsew")

    def open_keypad(self):
        if self.keypad_open:
            return
        self.keypad_open = True
        NumericKeypad(self.master, self.id_entry, on_close_cb=lambda: self.set_keypad_closed())

    def set_keypad_closed(self):
        self.keypad_open = False

    # ========= PREVIEW =========
    def show_preview_overlay(self):
        for w in self.master.winfo_children():
            w.destroy()

        overlay = ttk.Frame(self.master, padding=20)
        overlay.pack(fill="both", expand=True)

        center_frame = ttk.Frame(overlay)
        center_frame.pack(fill="both", expand=True)

        self.preview_label = ttk.Label(center_frame)
        self.preview_label.pack(anchor="center", expand=True)

        stop_btn = self.big_button(overlay, "STOP PREVIEW", self.close_preview_overlay)
        stop_btn.pack(pady=40, padx=60, ipady=BTN_PAD_Y, fill="x")

        self.preview_running = True
        self.update_preview()

    def update_preview(self):
        if not self.preview_running:
            return
        try:
            frame = self.picam2.capture_array()
            img = Image.fromarray(frame)

            screen_w = self.master.winfo_width()
            screen_h = self.master.winfo_height()

            max_w = screen_w - PREVIEW_MARGIN_W
            max_h = screen_h - PREVIEW_MARGIN_H

            ratio = img.width / img.height
            w = max_w
            h = int(w / ratio)
            if h > max_h:
                h = max_h
                w = int(h * ratio)

            img = img.resize((w, h))
            self.preview_img = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_img)
        except:
            pass

        self.master.after(120, self.update_preview)

    def close_preview_overlay(self):
        self.preview_running = False
        self.build_page1()

    # ========= RECORDING =========
    def start_recording(self):
        self.invoice_id = self.id_entry.get().strip()
        if not self.invoice_id:
            self.big_alert("Empty", "Please enter Invoice ID")
            return

        video_file = os.path.join(VIDEO_PATH, f"{self.invoice_id}.mp4")
        if os.path.exists(video_file):
            os.remove(video_file)

        self.encoder = H264Encoder(bitrate=3_000_000)
        self.output  = FfmpegOutput(video_file)
        self.picam2.switch_mode(self.video_cfg)
        time.sleep(0.3)
        self.picam2.start_recording(self.encoder, self.output)

        self.build_page2()

    def build_page2(self):
        for w in self.master.winfo_children():
            w.destroy()

        wrap = ttk.Frame(self.master, padding=30)
        wrap.pack(fill="both", expand=True)

        top = ttk.Frame(wrap)
        top.pack(pady=(8, 18))

        self.rec_title = ttk.Label(top, text=f"Recording: {self.invoice_id}",
                                   font=("Arial", 44, "bold"))
        self.rec_title.pack(side="left", padx=(0, 20))

        self.timer_label = ttk.Label(top, text="(00:00)", font=("Arial", 44, "bold"))
        self.timer_label.pack(side="left")

        self.rec_start_time = time.time()
        self.update_timer()

        self.cap_status = ttk.Label(wrap, text="", font=("Arial", 32))
        self.cap_status.pack(pady=18)

        # CAPTURE BUTTON HIDDEN
        # cap_btn = self.big_button(wrap, "CAPTURE INVOICE", self.capture_image)
        # cap_btn.pack(pady=32, padx=BTN_PAD_X, ipady=BTN_PAD_Y, fill="x")

        stop_btn = self.big_button(wrap, "STOP RECORDING", self.stop_recording)
        stop_btn.pack(pady=32, padx=BTN_PAD_X, ipady=BTN_PAD_Y, fill="x")

    def update_timer(self):
        elapsed = int(time.time() - self.rec_start_time)
        mm = elapsed // 60
        ss = elapsed % 60
        self.timer_label.config(text=f"({mm:02d}:{ss:02d})")
        self.master.after(1000, self.update_timer)

    def capture_image(self):
        img_file = os.path.join(IMAGE_PATH, f"{self.invoice_id}.jpg")
        try:
            frame = self.picam2.capture_array()
            Image.fromarray(frame).convert("RGB").save(img_file, "JPEG", quality=92)
            self.cap_status.config(text="âœ” Image Captured", foreground="green")
        except Exception as e:
            self.cap_status.config(text=f"âš  Capture failed: {e}", foreground="red")

    def stop_recording(self):
        # IMAGE CHECK REMOVED
        # img_file = os.path.join(IMAGE_PATH, f"{self.invoice_id}.jpg")
        # if not os.path.exists(img_file):
        #     self.big_alert("No Image", "Image is not captured. Please capture it.")
        #     return

        try:
            self.picam2.stop_recording()
        except:
            pass

        add_to_upload_queue(self.invoice_id)
        self.picam2.switch_mode(self.preview_cfg)
        self.build_page1()

    # ========= ALERT =========
    def big_alert(self, title, message):
        for w in self.master.winfo_children():
            if getattr(w, "_is_alert", False):
                w.destroy()

        alert = tk.Frame(self.master, bg="white", bd=4, relief="solid")
        alert._is_alert = True

        WIDTH, HEIGHT = 900, 420
        alert.place(relx=0.5, rely=0.5, anchor="center",
                    width=WIDTH, height=HEIGHT)

        tk.Label(alert, text=title,
                 font=("Arial", 60, "bold"),
                 bg="white").pack(pady=20)

        tk.Label(alert, text=message, wraplength=800,
                 font=("Arial", 38),
                 bg="white").pack(pady=10)

        def close_alert():
            alert.destroy()

        ok_btn = tk.Button(alert, text="OK",
                           font=("Arial", 48, "bold"),
                           bg="#2c3e50", fg="white",
                           relief="flat",
                           command=close_alert)
        ok_btn.pack(side="bottom", pady=25, ipadx=25, ipady=15, fill="x")

# =========================
# RUN APP
# =========================
if __name__ == "__main__":
    root = ttkbs.Window(themename="flatly")
    root.update_idletasks()
    root.attributes("-fullscreen", True)
    RecorderApp(root)
    root.mainloop()
