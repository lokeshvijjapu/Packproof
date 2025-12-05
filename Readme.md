

# 📘 PackProof Raspberry Pi Kiosk System 

This repository contains the complete codebase for the **PackProof Raspberry Pi Kiosk System**, designed for:

* Raspberry Pi Zero 2W / Raspberry Pi 4
* Touchscreen kiosk
* Continuous invoice video recording
* Automatic background uploading
* Offline-safe operation with UPS
* Safe shutdown + automatic restart using MOSFET auto-ON circuit



# 📁 **Project Structure**

```
/codes
│
├── app.py            # Main launcher (started by systemd)
├── main.py           # Recorder application (video capture UI)
├── uploader.py       # Background uploader (runs forever)
├── wifi.py           # Wi-Fi setup interface + custom keyboard
│
└── packproof/
      ├── videos/     # Saved recorded videos
      ├── images/     # Saved invoice images
      └── upload_log.json
```

---

# ⚡ **New: Automatic Safe Power Handling**

The system now works with a 5V UPS module + a custom IRL540N MOSFET circuit to achieve:

* ✔ Auto shutdown when main power is lost
* ✔ Safe video finalization before shutdown
* ✔ Automatic restart when power returns
* ✔ Prevent unwanted reboot if user presses button while Pi is ON

Details of the circuit are provided below.

---

# 🚀 **Boot Sequence**

### 1️⃣ `launcher.service` starts at boot

Starts only **after the full desktop is ready** (LightDM + LXDE).

### 2️⃣ `app.py` begins

App performs:

* Internet check (`ping 8.8.8.8`)
* If connected → start Recorder + Uploader
* If not connected → open Wi-Fi setup screen

### 3️⃣ `uploader.py` runs forever

Handles:

* Background upload
* Server wake
* Auto retry
* Removes successfully uploaded files

### 4️⃣ `power_monitor.service`

Runs continuously in background:

* Monitors GPIO26 for power loss
* Shows **fullscreen warning popup**
* Safely stops recording
* Flushes FS
* After 10 seconds → shutdowns Pi safely

---

# 🧠 **launcher.service (Updated – Must Use This Version)**

Create/edit:

```
/etc/systemd/system/launcher.service
```

Paste:

```ini
[Unit]
Description=Packproof Launcher (Full Kiosk)
After=display-manager.service
Wants=display-manager.service

[Service]
Type=simple
User=neonflake
WorkingDirectory=/home/neonflake/codes

Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/neonflake/.Xauthority

ExecStartPre=/bin/sleep 3
ExecStart=/usr/bin/python3 /home/neonflake/codes/app.py

Restart=always
RestartSec=2
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=display-manager.service
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable launcher.service
```

---

# 🔋 **power_monitor.service (Updated – Must Use This Version)**

Create/edit:

```
/etc/systemd/system/power_monitor.service
```

Paste:

```ini
[Unit]
Description=Power Loss Monitor
After=display-manager.service
Wants=display-manager.service

[Service]
Type=simple
User=root

WorkingDirectory=/home/neonflake/codes
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/neonflake/.Xauthority

ExecStart=/usr/bin/python3 /home/neonflake/codes/power_monitor.py
Restart=always
RestartSec=2

[Install]
WantedBy=display-manager.service
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable power_monitor.service
```

---

# 🔥 **Safe Power Monitor Logic**



## 🟦 GPIO26 — Mains Power Detection Input

Your UPS provides **IN+ = 5V only when mains power is present**.  
This cannot be connected directly to a Raspberry Pi GPIO because:

- Raspberry Pi GPIO maximum safe input is **3.3V**
- UPS IN+ outputs **5V**

So a **resistor divider** is required.

---

### ✔ Resistor Divider Network

- **100 kΩ (R1)** from **UPS IN+ → GPIO26**
- **7.3 kΩ (R2)** from **GPIO26 → GND**

### 🔧 Divider Output Voltage:

\[
V_{gpio} = 5V \times \frac{7.3k}{100k + 7.3k} \approx 0.36V
\]

So:

- When **UPS IN+ = 0V** → GPIO26 = **0V (LOW)**
- When **UPS IN+ = 5V** → GPIO26 = **0.36V (still LOW)**

This UPS module uses **reverse logic**:

- **UPS OUT = 5V always** (Pi stays ON from battery)
- **UPS IN+ = 5V only when mains is present**

The divider protects the GPIO and ensures stable detection.



### ✔ Benefits of the 100kΩ + 7.3kΩ Divider

- GPIO26 only receives **safe, low-level signals**
- No over-voltage risk to Pi
- Prevents false triggering
- Fully isolated from UPS circuitry



### 🧲 GPIO26 Wiring Diagram


UPS IN+ (5V) ───► 100kΩ ───► GPIO26 ───► 7.3kΩ ───► GND





### 🧠 Logic Used in `power_monitor.py`

- **GPIO26 = HIGH (1)** → Mains power is **present**
- **GPIO26 = LOW (0)** → **Power loss detected**, start shutdown countdown




---
`power_monitor.py`:

* Watches GPIO26 (UPS mains detect)
* When main power goes LOW:

  * Displays big fullscreen popup
  * Stops FFmpeg safely (SIGINT)
  * Syncs filesystem
  * Waits 10 seconds
  * Performs clean shutdown

Popup shown:

```
⚠ POWER LOST ⚠

Saving Video…
System will Shut Down Safely.
```

---

🔥 Relay-Based Automatic Safe Power Control (Updated Circuit)

This new relay circuit replaces the old MOSFET RUN-pin design.

It ensures:

✔ Pi turns ON whenever adapter power is available

✔ Pi stays powered on battery during shutdown

✔ Pi is completely disconnected after shutdown

✔ Battery does NOT drain overnight

✔ Pi auto-boots again when adapter power returns

🧲 Step-by-Step Wiring — Final Verified Circuit

Below is the full wiring description of your working circuit.

🔹 UPS Module Connections

Adapter +5V → UPS IN+

Adapter GND → UPS IN-

Battery + → UPS B+

Battery – → UPS B-

Pi power comes from UPS OUT+ / OUT- (through relay)

🔹 Relay Coil Driver (BC547)

Relay coil + connects to UPS OUT+

Relay coil – connects to BC547 collector

BC547 emitter connects to GND

Flyback diode:

1N4007 diode across relay coil

Stripe (cathode) → relay coil + (UPS OUT+)

Non-stripe (anode) → relay coil – (BC547 collector)

This protects the transistor.

🔹 Base Drive Logic (to keep relay ON during shutdown)

UPS IN+ connects to BC547 base through a 4.7k resistor

This keeps the relay ON whenever adapter power is available.

GPIO6 connects to a diode (1N4148 or 1N4007)

Anode → GPIO6

Cathode (stripe) → 2.2k resistor → BC547 base

This keeps the relay ON while the Pi is ON.

A 100k resistor connects BC547 base to GND

Ensures the transistor turns OFF cleanly when both power and GPIO6 go LOW.

🔹 Relay Contact Connections

Relay NO (Normally Open) → UPS OUT+

Relay COM → Pi 5V input (GPIO pin 2 or 4)

Relay NC is not used

UPS OUT- → Pi GND

This ensures:

When relay is ON → Pi gets 5V

When relay is OFF → Pi is fully isolated (0V drain)

# 🎞 **main.py — Recorder Application**

Provides:

* Fullscreen kiosk UI
* Invoice entry (with on-screen numeric keypad)
* Live camera preview
* Start/stop video recording
* Invoice image capture
* Saves videos to:

```
/home/neonflake/packproof/videos/<invoice>.mp4
```

* Adds invoice to upload queue

---

# 📤 **uploader.py — Background Video Uploader**

Handles:

* Queue (upload_log.json)
* Video upload
* Async retries
* Removes files after upload
* Survives power loss
* Runs forever

---

# 📶 **wifi.py — Custom Wi-Fi Setup**

Features:

* Fullscreen
* Large scrollable list
* Touch friendly
* Custom on-screen keyboard
* Hidden SSIDs supported
* Auto-connect enabled

---

# 🛠 Troubleshooting

### ❌ Popup not showing

Fix: power_monitor.service must include:

```
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/neonflake/.Xauthority
After=display-manager.service
```

### ❌ Kiosk sometimes windowed / titlebar visible

Fix: launcher.service must use:

```
After=display-manager.service
ExecStartPre=/bin/sleep 3
```

### ❌ SSH not connecting

Usually caused by Wi-Fi not connected.
Run:

```
nmcli device status
hostname -I
```

---

# 🎯 Final Notes

This system is tuned for:

* Raspberry Pi Zero 2W
* Picamera2
* Tkinter + ttkbootstrap GUI
* UPS-safe operation
* Continuous background uploading
* Auto-Kiosk mode
* Automatic restart on power recovery

---
