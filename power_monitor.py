#!/usr/bin/env python3
# Power Monitor with animated shutdown screen + VIDEO RECOVERY (FULLY ROBUST)

import lgpio
import time
import subprocess
import os
import sys
import threading
import json
from datetime import datetime


CHIP = 0
POWER_PIN = 26
TIMEOUT_SECONDS = 1      # shutdown delay

VIDEO_DIR = "/home/neonflake/packproof/videos"
UPLOAD_LOG = "/home/neonflake/packproof/upload_log.json"


# -----------------------------------------------------
# LOGGING
# -----------------------------------------------------
def log(msg):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


# -----------------------------------------------------
# ADD LOST VIDEOS TO UPLOAD QUEUE
# -----------------------------------------------------
def recover_pending_videos():
    data = {"pending": [], "uploaded": []}

    # Load existing log
    if os.path.exists(UPLOAD_LOG):
        try:
            with open(UPLOAD_LOG, "r") as f:
                data = json.load(f)
        except:
            pass

    # Scan video folder
    for filename in os.listdir(VIDEO_DIR):
        if filename.endswith(".mp4"):
            order_id = filename.replace(".mp4", "")
            log(f"Recovered video: {order_id}")
            data["pending"].append({"id": order_id})

    # Save updated log
    with open(UPLOAD_LOG, "w") as f:
        json.dump(data, f, indent=2)

    log("Recovery completed.")


# -----------------------------------------------------
# SHUTDOWN SCREEN THREAD
# -----------------------------------------------------
def show_shutdown_screen_thread():
    import tkinter as tk

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)

    w = root.winfo_screenwidth()
    h = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+0+0")
    root.configure(bg="black")

    title = tk.Label(
        root,
        text="SWITCHING OFF",
        font=("Arial", 120, "bold"),
        fg="white",
        bg="black"
    )
    title.pack(expand=True)

    saving = tk.Label(
        root,
        text="Saving data",
        font=("Arial", 50),
        fg="white",
        bg="black"
    )
    saving.pack(pady=50)

    dots = ["", ".", "..", "..."]
    i = 0

    def animate():
        nonlocal i
        saving.config(text=f"Saving data{dots[i]}")
        i = (i + 1) % 4
        saving.after(400, animate)

    animate()
    root.mainloop()


def show_shutdown_screen():
    if "DISPLAY" not in os.environ:
        log("DISPLAY missing — skipping GUI.")
        return

    t = threading.Thread(target=show_shutdown_screen_thread, daemon=True)
    t.start()
    log("Shutdown screen started.")


# -----------------------------------------------------
# FINALIZE VIDEO & SHUTDOWN
# -----------------------------------------------------
def finalize_and_shutdown():
    log("Power lost → safe shutdown started.")

    show_shutdown_screen()

    try:
        subprocess.call(["pkill", "-2", "ffmpeg"])
        log("Stopped ffmpeg safely.")
    except:
        pass

    time.sleep(3)
    subprocess.call(["sync"])
    subprocess.call(["sudo", "shutdown", "-h", "now"])


# -----------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------
def main():
    # 🔥 RECOVER LOST VIDEOS ON STARTUP
    recover_pending_videos()

    try:
        chip = lgpio.gpiochip_open(CHIP)
    except Exception as e:
        log(f"Cannot open gpiochip: {e}")
        sys.exit(1)

    try:
        lgpio.gpio_claim_input(chip, POWER_PIN, lgpio.SET_PULL_DOWN)
    except Exception as e:
        log(f"Cannot claim GPIO{POWER_PIN}: {e}")
        lgpio.gpiochip_close(chip)
        sys.exit(1)

    log("Power monitor running.")
    log(f"Timeout = {TIMEOUT_SECONDS}s")

    mains_off_since = None

    try:
        while True:
            state = lgpio.gpio_read(chip, POWER_PIN)

            if state == 1:
                # 🔥 if power just returned → recover AGAIN
                if mains_off_since is not None:
                    log("Power returned → recovering videos.")
                    recover_pending_videos()

                mains_off_since = None

            else:
                if mains_off_since is None:
                    mains_off_since = time.time()
                    log("Power lost → countdown started.")

                elif time.time() - mains_off_since >= TIMEOUT_SECONDS:
                    finalize_and_shutdown()
                    mains_off_since = None

            time.sleep(0.2)

    except KeyboardInterrupt:
        log("Monitor stopped manually.")

    finally:
        lgpio.gpiochip_close(chip)
        log("GPIO released. Power monitor stopped.")


if __name__ == "__main__":
    main()
