This repository contains the full codebase for the **PackProof Raspberry Pi Kiosk System**.
The system performs:

* **Invoice video recording**
* **Automatic background uploading**
* **Wi-Fi setup UI (touchscreen keyboard)**
* **Boot-time launcher with intelligent internet detection**
* **Full kiosk fullscreen UI**

Designed for **Raspberry Pi Zero 2 W / Pi 4** with a touchscreen (HDMI display + SPI touch).

---

# 📁 **Project Structure**

```
/codes
│
├── app.py           # Main entry point (runs on boot via systemd)
├── main.py          # Recorder application (video capture)
├── uploader.py      # Background uploader (runs forever)
├── wifi.py          # Wi-Fi setup UI + fullscreen keyboard
│
└── packproof/
      ├── videos/    # Recorded videos saved here
      ├── images/    # Optional image captures
      └── upload_log.json
```

---

# 🚀 **Boot Sequence**

### 1️⃣ launcher.py starts at boot

(systemd autostart)

### 2️⃣ launcher.py checks internet

Fast method:

```
ping -c1 -W1 8.8.8.8
```

### Behavior:

| Internet Status   | Result                                                              |
| ----------------- | ------------------------------------------------------------------- |
| **Connected**     | Skip Wi-Fi → start Recorder + background uploader                   |
| **Not connected** | Open Wi-Fi UI → user selects network → on success → launch Recorder |

### 3️⃣ uploader.py runs in background **always**

Does not interrupt recorder.

---

# 📜 **launcher.py — Main Auto Launcher**

**Features:**

* Fast internet check
* Background uploader thread
* Automatic Wi-Fi setup fallback
* Auto-start Recorder after internet connects
* GUI-safe (DISPLAY + XAUTHORITY handling is done via systemd)

This file orchestrates the entire system.

---

# 🎥 **main.py — Recorder Application**

**Functions:**

* Fullscreen kiosk UI
* Enter invoice ID
* Start/stop video recording
* Live preview
* Automatically adds invoice to upload queue
* Saves video to:

```
/home/neonflake/packproof/videos/<invoice>.mp4
```

Uses:

* **Picamera2**
* **ttkbootstrap**
* **PIL**

No keyboard required (uses numeric keypad overlay).

---

# 📤 **uploader.py — Background File Uploader**

Runs **forever** in a loop:

* Checks `/packproof/upload_log.json`
* Uploads pending videos (and optional images)
* Deletes them after successful upload
* Handles server cold-start delays
* Auto-retries on failure

Endpoints used:

```
WAKE_URL  = https://visitwise.claricall.space
API_URL   = https://visitwise.claricall.space/api/videos/add
```

Runs fully in the background (daemon thread started by launcher.py).

---

# 📶 **wifi.py — Wi-Fi Kiosk UI**

Custom fullscreen Wi-Fi selection interface with:

* Touch-friendly buttons
* Large scrolling list
* Secure password handling
* Fullscreen custom keyboard with

  * ABC mode
  * 123 mode
  * SYM mode
* Supports hidden SSIDs
* Auto-configures autoconnect:

```
nmcli connection modify <ssid> connection.autoconnect yes
```

Used only when internet is not available at boot.

---

# 🔧 **Systemd Autostart Service**

Create file:

```
sudo nano /etc/systemd/system/launcher.service
```

Paste:

```ini
[Unit]
Description=Packproof Launcher
After=graphical.target

[Service]
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/neonflake/.Xauthority
ExecStart=/usr/bin/python3 /home/neonflake/codes/app.py
Restart=always
User=neonflake
WorkingDirectory=/home/neonflake/codes

[Install]
WantedBy=graphical.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable launcher.service
sudo systemctl start launcher.service
```

Check status:

```bash
sudo systemctl status launcher.service
```

---

# 🏃 **Manual Run (for testing)**

### Run Wi-Fi setup:

```
python3 wifi.py
```

### Run Recorder:

```
python3 main.py
```

### Run Uploader:

```
python3 uploader.py
```

### Run app:

```
python3 app.py
```

---

# ❗ Troubleshooting

### ❌ Error: `no display name and no $DISPLAY variable`

Systemd started GUI before X server.
Fix: Ensure service is `After=graphical.target` and includes:

```
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/neonflake/.Xauthority
```

---

### ❌ Touchscreen works but display small

Launcher opens **before resolution config loaded**.
Set resolution in `/boot/firmware/config.txt`:

```
hdmi_group=2
hdmi_mode=87
hdmi_cvt=480 320 60 6 0 0 0
```

---

### ❌ Videos not uploading

Check log:

```
cat /home/neonflake/packproof/upload_log.json
```

Also check service:

```
systemctl status launcher.service
```

---

# 📌 Version Notes

This system was designed for:

* Raspberry Pi Zero 2W
* Picamera2
* Python 3.11
* Tkinter / ttkbootstrap
* NetworkManager (nmcli)
