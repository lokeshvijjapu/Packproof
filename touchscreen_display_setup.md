Great — I read your documentation file completely ✔ and I understand you want to **add a clean, simple, easy-to-understand section in the README about the touchscreen display setup**, so that any new user reading the README will immediately know:

* What display you used
* How it connects
* What drivers are needed
* What config.txt entries to add
* How to calibrate touch
* How to troubleshoot
* Everything step-by-step

I will now give you **the perfect README section** that you can directly copy-paste into your documentation.
This section is written **clearly**, **beginner-friendly**, and follows the same format as your existing documentation.
It also references the Waveshare wiki you mentioned in the document. 

---

# ✅ **README Section: 3.5" Touchscreen Display Setup (Waveshare)**

## **1. Display Model**

This project uses the **Waveshare 3.5" HDMI Touchscreen (SPI Touch)**.

* **Video Output:** HDMI
* **Touch Interface:** SPI (ADS7846 driver)
* **Resolution:** 480×320
* **Touch Type:** Resistive (works with finger or stylus)

---

## **2. Physical Connections**

### **HDMI (Video)**

Connect the HDMI cable from Raspberry Pi Zero 2 W → Waveshare 3.5" HDMI input.

### **Touch (SPI Interface)**

Touch signals are transferred through GPIO pins using SPI.
Connect the 26-pin header of the display to the Pi's GPIO header.

The important pins used:

| Touch Signal | Pi Pin |
| ------------ | ------ |
| MOSI         | GPIO10 |
| MISO         | GPIO9  |
| SCK          | GPIO11 |
| CS           | GPIO8  |
| PENIRQ       | GPIO25 |
| 5V / 3.3V    | Power  |
| GND          | Ground |

No additional wiring is required if the display directly plugs onto the GPIO header.

---

## **3. Enable Touchscreen in config.txt**

Edit:

```
sudo nano /boot/firmware/config.txt
```

Add:

```
dtparam=spi=on
dtoverlay=ads7846,penirq=25,cs=1,speed=2000000,keep_vref_on=1,swapxy=0,xmin=200,xmax=3900,ymin=200,ymax=4095
```

Save and reboot:

```
sudo reboot
```

Touch will now work with default calibration.

---

## **4. Touch Calibration (Important)**

Resistive touchscreens often need calibration.
Install calibrator:

```
sudo apt install xinput-calibrator
```

Run it inside the desktop environment:

```
xinput_calibrator
```

It will display four calibration points.
At the end, it prints something like:

```
Option "Calibration" "208 3710 473 3780"
Option "SwapAxes" "0"
```

Add these values to:

```
sudo mkdir -p /etc/X11/xorg.conf.d
sudo nano /etc/X11/xorg.conf.d/99-calibration.conf
```

Paste:

```
Section "InputClass"
    Identifier "ADS7846 touch calibration"
    MatchProduct "ADS7846 Touchscreen"
    Option "Calibration" "208 3710 473 3780"
    Option "SwapAxes" "0"
EndSection
```

Reboot.

Touch is now correctly aligned.

---

## **5. How Resistive Touch Works (Why Stylus Works Better Than Finger)**

* Finger covers a wide area → pressure spreads → coordinate noise increases
* Stylus has a small point → accurate and centered pressure → perfect coordinates
* Resistive screens are not designed for multi-touch → only single-point pressure is stable

This is normal behavior for this type of display.

---

## **6. Troubleshooting**

### **Touch is Inverted / Axis Flipped**

Edit the config.txt touch overlay:

```
swapxy=1
```

or flip ranges:

```
xmin <-> xmax
ymin <-> ymax
```

### **Touch Only Works with Stylus**

Increase pressure recognition:

```
Option "EmulateThirdButton" "1"
```

### **Calibration Off by Small Margin**

Re-run:

```
evtest /dev/input/eventX
```

Tap all four corners and update Calibration values accordingly.

---

## **7. Official Reference**

Waveshare setup guide:
[https://www.waveshare.com/wiki/3.5inch_HDMI_LCD](https://www.waveshare.com/wiki/3.5inch_HDMI_LCD)

---