#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkbs
from ttkbootstrap.constants import *
# camera imports (keep as you had them)
try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FfmpegOutput
except Exception:
    Picamera2 = None
    H264Encoder = None
    FfmpegOutput = None

from PIL import Image, ImageTk
import os, time, json, subprocess, shlex

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
TITLE_FONT      = ("Arial", 54, "bold")
ENTRY_FONT      = ("Arial", 48)
ENTRY_IPADY     = 32

# =========================
# Helpers - nmcli check
# =========================
def run_cmd_list(cmd_list, timeout=4):
    """Run command list and return (rc, stdout)."""
    try:
        p = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip()
    except Exception:
        return 1, ""

def check_online():
    """Return True when any active WiFi connection exists (nmcli)."""
    # first try to get active wifi line
    rc, out = run_cmd_list(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"])
    if rc == 0 and out:
        for line in out.splitlines():
            if line.startswith("yes:") or line.startswith("yes:"):
                return True
    # fallback: check device connection
    rc2, out2 = run_cmd_list(["nmcli", "-t", "-f", "STATE", "general"])
    if rc2 == 0 and "connected" in out2.lower():
        return True
    return False

# =========================
# Queue handler
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
        print(f"[queue] Added {order_id}")

# =========================
# Numeric keypad (full screen)
# =========================
class NumericKeypad(tk.Toplevel):
    def __init__(self, master, target_entry, on_close_cb=None):
        super().__init__(master)
        self.target = target_entry
        self.on_close_cb = on_close_cb

        self.overrideredirect(True)
        self.configure(bg="white")
        # make large enough to cover most displays; you can change for your exact screen.
        self.geometry("1280x720+0+0")
        self.after(50, lambda: self.grab_set())

        root = tk.Frame(self, bg="white")
        root.place(relx=0, rely=0, relwidth=1, relheight=1)

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
                          font=("Arial", 40), bg="#2c3e50", fg="white", relief="flat")
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

        ok = tk.Button(bottom, text="OK", font=("Arial", 40, "bold"),
                       bg="#1f8a50", fg="white", relief="flat", command=self.finish)
        ok.grid(row=0, column=0, padx=18, pady=10, sticky="nsew")

        back = tk.Button(bottom, text="BACK", font=("Arial", 40, "bold"),
                         bg="#8a2b2b", fg="white", relief="flat", command=self.close_only)
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
            try:
                self.on_close_cb()
            except:
                pass

# =========================
# Main app
# =========================
class RecorderApp:
    def __init__(self, master):
        self.master = master
        master.configure(bg="white")
        master.bind("<Escape>", lambda e: master.destroy())

        # style for start button (reduced padding to ensure it fits)
        self.style = ttkbs.Style()
        self.style.configure(
            "Start.TButton",
            font=(BTN_FONT_FAMILY, BTN_FONT_SIZE, "bold"),
            background="#FF8C00",
            foreground="black",
            padding=(20, 45)   # reduced from very large so text fits
        )
        self.style.map("Start.TButton",
                       background=[("active", "#FF8C00"),
                                   ("pressed", "#FF8C00"),
                                   ("hover", "#FF8C00")])

        # picamera2 initialization only if available
        if Picamera2:
            try:
                self.picam2 = Picamera2()
                self.preview_cfg = self.picam2.create_preview_configuration(main={"size": (640, 480)})
                self.video_cfg = self.picam2.create_video_configuration(main={"size": (640, 480)})
                self.picam2.configure(self.preview_cfg)
                self.picam2.start()
            except Exception:
                self.picam2 = None
        else:
            self.picam2 = None

        self.keypad_open = False
        self.preview_running = False

        self.build_home()

        # start online checker loop
        self.master.after(800, self.update_online_status)

    def build_home(self):
        for w in self.master.winfo_children():
            w.destroy()

        # top bar
        top = tk.Frame(self.master, bg="white")
        top.pack(fill="x", side="top")

        # ONLINE/OFFLINE label (solid dot + text)
        self.online_label = tk.Label(top, text="● ONLINE", font=("Arial", 36, "bold"),
                                     bg="white", fg="black")
        self.online_label.pack(side="left", padx=20, pady=10)

        # large settings icon
        tk.Button(top, text="⚙️", font=("Arial", 72, "bold"),
                  bg="white", fg="black", relief="flat",
                  command=self.open_settings).pack(side="right", padx=24, pady=8)

        # main wrapper - reduced top/bottom padding to make space
        wrapper = tk.Frame(self.master, bg="white")
        wrapper.pack(fill="both", expand=True, padx=36, pady=(8,18))

        tk.Label(wrapper, text="Enter Order ID", font=TITLE_FONT, bg="white").pack(pady=(10, 18))

        # thick black border frame
        border_frame = tk.Frame(wrapper, bg="black", bd=10, relief="solid")
        border_frame.pack(fill="x", pady=(6, 30))

        self.id_entry = tk.Entry(border_frame, font=ENTRY_FONT, justify="center",
                                 bg="white", fg="black", relief="flat")
        self.id_entry.pack(fill="x", ipady=ENTRY_IPADY, ipadx=18)

        # keypad should open only when tapping the entry
        self.id_entry.bind("<Button-1>", lambda e: self.open_keypad())

        # START button - ensure visible by using pack after packing wrapper; give some vertical padding
        ttkbs.Button(wrapper, text="START RECORDING", style="Start.TButton",
                     command=self.start_recording).pack(fill="x", pady=(20, 28))

    def update_online_status(self):
        try:
            online = check_online()
        except Exception:
            online = False

        if online:
            # green dot + ONLINE text (solid bullet)
            self.online_label.config(text="●  ONLINE", fg="green")
        else:
            self.online_label.config(text="●  OFFLINE", fg="red")

        # schedule again
        self.master.after(3000, self.update_online_status)

    def open_settings(self):
        for w in self.master.winfo_children():
            w.destroy()

        top = tk.Frame(self.master, bg="white")
        top.pack(fill="x", side="top")

        tk.Label(top, text="Settings", font=TITLE_FONT, bg="white").pack(side="left", padx=24, pady=12)

        tk.Button(top, text="⬅", font=("Arial", 48), bg="white", relief="flat",
                  command=self.build_home).pack(side="right", padx=20, pady=12)

        wrapper = tk.Frame(self.master, bg="white")
        wrapper.pack(fill="both", expand=True, padx=36, pady=36)

        # large option buttons
        self.big_button(wrapper, "SET CAMERA ANGLE", self.show_preview).pack(fill="x", pady=20)
        self.big_button(wrapper, "WI-FI SETTINGS", self.open_wifi).pack(fill="x", pady=20)
        self.big_button(wrapper, "BACK", self.build_home).pack(fill="x", pady=20)

    def open_wifi(self):
        # launch wifi.py in background, keep main app running
        # adjust path if your wifi.py is in /home/neonflake/codes/wifi.py
        try:
            subprocess.Popen(["python3", "/home/neonflake/codes/wifi.py"])
        except Exception as e:
            print("Failed to launch wifi UI:", e)

    def show_preview(self):
        for w in self.master.winfo_children():
            w.destroy()

        frame = tk.Frame(self.master, bg="white")
        frame.pack(fill="both", expand=True)

        self.preview_label = tk.Label(frame, bg="white")
        self.preview_label.pack(expand=True, fill="both")

        self.big_button(frame, "STOP PREVIEW", self.build_home).pack(fill="x", pady=18)

        self.preview_running = True
        self._update_preview()

    def _update_preview(self):
        if not self.preview_running:
            return
        if self.picam2:
            try:
                frame = self.picam2.capture_array()
                img = ImageTk.PhotoImage(Image.fromarray(frame))
                self.preview_label.config(image=img)
                self.preview_label.image = img
            except Exception:
                pass
        self.master.after(120, self._update_preview)

    def start_recording(self):
        oid = self.id_entry.get().strip()
        if not oid:
            self.show_alert("Empty", "Please enter Order ID")
            return

        outfile = os.path.join(VIDEO_PATH, f"{oid}.mp4")
        try:
            if os.path.exists(outfile):
                os.remove(outfile)
        except:
            pass

        if self.picam2 and H264Encoder and FfmpegOutput:
            try:
                self.encoder = H264Encoder(bitrate=3_000_000)
                self.output = FfmpegOutput(outfile)
                self.picam2.switch_mode(self.video_cfg)
                time.sleep(0.3)
                self.picam2.start_recording(self.encoder, self.output)
            except Exception as e:
                print("Recording start failed:", e)
                self.show_alert("Error", "Failed to start recording")
                return
        else:
            # if camera not available, just create an empty placeholder file
            open(outfile, "wb").close()

        self.build_record_screen(oid)

    def build_record_screen(self, oid):
        for w in self.master.winfo_children():
            w.destroy()

        wrap = tk.Frame(self.master, bg="white", padx=28, pady=28)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text=f"Recording: {oid}", font=("Arial", 40, "bold"), bg="white").pack(pady=10)
        self.timer_label = tk.Label(wrap, text="(00:00)", font=("Arial", 36, "bold"), bg="white")
        self.timer_label.pack()

        self.rec_start_time = time.time()
        self._update_timer()

        self.big_button(wrap, "STOP RECORDING", self.stop_recording).pack(fill="x", pady=18)
        self.current_oid = oid

    def _update_timer(self):
        try:
            elapsed = int(time.time() - self.rec_start_time)
            mm, ss = elapsed // 60, elapsed % 60
            self.timer_label.config(text=f"({mm:02d}:{ss:02d})")
        except:
            pass
        self.master.after(1000, self._update_timer)

    def stop_recording(self):
        try:
            if self.picam2:
                self.picam2.stop_recording()
        except:
            pass

        try:
            add_to_upload_queue(self.current_oid)
        except:
            pass

        try:
            if self.picam2:
                self.picam2.switch_mode(self.preview_cfg)
        except:
            pass

        self.build_home()

    def open_keypad(self):
        if self.keypad_open:
            return
        self.keypad_open = True
        NumericKeypad(self.master, self.id_entry, on_close_cb=self._keypad_closed)

    def _keypad_closed(self):
        self.keypad_open = False

    def big_button(self, parent, text, cmd):
        return tk.Button(parent, text=text,
                         font=("Arial", 44, "bold"),
                         bg="#2c3e50", fg="white",
                         height=2, relief="flat", command=cmd)

    def show_alert(self, title, message):
        win = tk.Toplevel(self.master)
        win.overrideredirect(True)
        win.geometry("900x420+200+150")
        win.configure(bg="white")
        tk.Label(win, text=title, font=("Arial", 60, "bold"), bg="white").pack(pady=20)
        tk.Label(win, text=message, font=("Arial", 36), bg="white").pack(pady=10)
        tk.Button(win, text="OK", font=("Arial", 48), bg="#2c3e50", fg="white",
                  relief="flat", command=win.destroy).pack(fill="x", pady=20)

# =========================
# Run
# =========================
if __name__ == "__main__":
    root = ttkbs.Window(themename="flatly")
    # use after to set fullscreen reliably
    root.after(50, lambda: root.attributes("-fullscreen", True))
    RecorderApp(root)
    root.mainloop()
