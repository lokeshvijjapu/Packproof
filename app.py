#!/usr/bin/env python3
import subprocess, threading, time, os, sys
import tkinter as tk

# Paths to your three modules
WIFI_SCRIPT     = "/home/neonflake/codes/wifi.py"
RECORDER_SCRIPT = "/home/neonflake/codes/main.py"
UPLOADER_SCRIPT = "/home/neonflake/codes/uploader.py"

# ======================================================
# FAST INTERNET CHECK (0.1 sec)
# ======================================================
def has_internet():
    try:
        # Ping 8.8.8.8 once, 1-second timeout
        subprocess.check_output(
            ["ping", "-c", "1", "-W", "1", "8.8.8.8"],
            stderr=subprocess.DEVNULL
        )
        return True
    except:
        return False

# ======================================================
# RUN A PYTHON FILE IN CURRENT INTERPRETER
# ======================================================
def run_python_script(path):
    os.system(f"python3 {path}")

# ======================================================
# UPLOADER THREAD
# ======================================================
def start_uploader():
    def worker():
        os.system(f"python3 {UPLOADER_SCRIPT}")
    t = threading.Thread(target=worker, daemon=True)
    t.start()

# ======================================================
# WIFI LAUNCHER
# ======================================================
def start_wifi():
    print("ðŸ“¶ No internet â€” opening Wi-Fi setup...")
    os.system(f"python3 {WIFI_SCRIPT}")  
    # When wifi.py exits â†’ return to launcher
    print("ðŸ“¶ Wi-Fi window closed. Checking internet again...")

# ======================================================
# RECORDER LAUNCH
# ======================================================
def start_recorder():
    print("ðŸŽ¥ Starting Recorder...")
    os.system(f"python3 {RECORDER_SCRIPT}")

# ======================================================
# MAIN LOGIC
# ======================================================
def main():
    print("ðŸ” Checking Internet...")
    
    # --- Start uploader immediately (always running) ---
    start_uploader()

    # --- First check ---
    if has_internet():
        print("ðŸŒ Internet already available. Skipping Wi-Fi.")
        start_recorder()
        return

    # --- No internet â†’ start Wi-Fi setup ---
    start_wifi()

    # After Wi-Fi window closes â†’ check internet again
    if has_internet():
        print("ðŸŒ Wi-Fi connected successfully.")
        start_recorder()
    else:
        print("âŒ Still no internet. Restarting Wi-Fi...")
        start_wifi()  # retry
        if has_internet():
            start_recorder()
        else:
            # Fail-safe â€“ show message on screen
            root = tk.Tk()
            root.attributes("-fullscreen", True)
            tk.Label(root, text="NO INTERNET.\nCannot continue.",
                     font=("Arial", 32), fg="red").pack(expand=True)
            root.mainloop()

if __name__ == "__main__":
    main()
