#!/usr/bin/env python3
# Power Monitor with 10-second shutdown + fullscreen popup

import lgpio
import time
import subprocess
import os
import sys
from datetime import datetime

CHIP = 0
POWER_PIN = 26
TIMEOUT_SECONDS = 10     # 10 SEC SHUTDOWN DELAY


# -----------------------------------------------------
# LOGGING
# -----------------------------------------------------
def log(msg):
    t = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t}] {msg}", flush=True)


# -----------------------------------------------------
# FULLSCREEN POPUP (if GUI exists)
# -----------------------------------------------------
def show_shutdown_popup():
    if "DISPLAY" not in os.environ:
        log("DISPLAY not found — skipping popup.")
        return None

    try:
        import tkinter as tk

        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.configure(bg="white")
        root.attributes("-topmost", True)

        message = (
            "⚠ POWER LOST ⚠\n\n"
            "Saving Video…\n"
            "System will Shut Down Safely."
        )

        label = tk.Label(
            root,
            text=message,
            font=("Arial", 70, "bold"),
            fg="red",
            bg="white",
            justify="center"
        )
        label.pack(expand=True)

        root.update()
        return root

    except Exception as e:
        log(f"Popup error: {e}")
        return None


# -----------------------------------------------------
# FINALIZE RECORDING + SHUTDOWN
# -----------------------------------------------------
def finalize_and_shutdown():
    log("Power lost >= 10 seconds — initiating safe shutdown.")

    # 1. Fullscreen popup
    popup = show_shutdown_popup()

    # 2. Stop ffmpeg safely
    try:
        subprocess.call(["pkill", "-2", "ffmpeg"])
        log("Sent SIGINT to ffmpeg for finalizing video.")
    except Exception as e:
        log(f"Failed to signal ffmpeg: {e}")

    time.sleep(2)

    # 3. Sync filesystem
    try:
        subprocess.call(["sync"])
        log("Filesystem sync complete.")
    except Exception as e:
        log(f"sync() failed: {e}")

    # 4. Shutdown
    try:
        subprocess.call(["sudo", "shutdown", "-h", "now"])
    except Exception as e:
        log(f"Shutdown failed: {e}")


# -----------------------------------------------------
# MAIN MONITOR
# -----------------------------------------------------
def main():
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

    log("Power monitor started.")
    log(f"Shutdown timeout = {TIMEOUT_SECONDS} seconds")

    mains_off_since = None
    last_state = lgpio.gpio_read(chip, POWER_PIN)
    log(f"Initial state = {last_state}")

    try:
        while True:
            current = lgpio.gpio_read(chip, POWER_PIN)

            # mains present
            if current == 1:
                if mains_off_since is not None:
                    log("Mains returned — countdown cancelled.")
                mains_off_since = None

            # mains lost
            else:
                if mains_off_since is None:
                    mains_off_since = time.time()
                    log("Mains is OFF — 10 second countdown started.")
                else:
                    elapsed = time.time() - mains_off_since
                    if elapsed >= TIMEOUT_SECONDS:
                        finalize_and_shutdown()
                        mains_off_since = None

            last_state = current
            time.sleep(0.2)

    except KeyboardInterrupt:
        log("Monitor stopped manually.")

    except Exception as e:
        log(f"Exception: {e}")

    finally:
        try:
            lgpio.gpiochip_close(chip)
        except:
            pass
        log("Power monitor stopped.")


if __name__ == "__main__":
    main()