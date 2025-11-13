#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import subprocess, shlex, threading, time, sys

DISPLAY_W, DISPLAY_H = 480, 320
REFRESH_INTERVAL = 6
DEFAULT_BUTTON_BG = "#d9d9d9"
KEYBOARD_FONT = ("Arial", 18, "bold")
LIST_FONT = ("Arial", 18, "bold")

def run_cmd(cmd, timeout=30):
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)

def bg_thread(fn):
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return t

def scan_wifi_once():
    run_cmd("nmcli device wifi rescan")
    rc, out, err = run_cmd("nmcli -t -f SSID,SECURITY,SIGNAL device wifi list")
    nets = []
    if rc != 0 or not out:
        return nets
    for line in out.splitlines():
        parts = line.split(":", 2)
        while len(parts) < 3:
            parts.append("")
        ssid, sec, sigs = parts[0], parts[1], parts[2]
        try:
            sig = int(sigs) if sigs else 0
        except:
            sig = 0
        if ssid.strip() == "":
            continue
        nets.append({"ssid": ssid, "security": sec, "signal": sig})
    dedup = {}
    for n in nets:
        s = n["ssid"]
        if s not in dedup or n["signal"] > dedup[s]["signal"]:
            dedup[s] = n
    nets = list(dedup.values())
    nets.sort(key=lambda x: x["signal"], reverse=True)
    return nets

def get_active_ssid():
    rc, out, err = run_cmd("nmcli -t -f ACTIVE,SSID dev wifi")
    if rc != 0 or not out:
        return None
    for line in out.splitlines():
        if not line: continue
        a, ssid = (line.split(":",1) + [""])[:2]
        if a == "yes":
            return ssid
    return None

class ConnectingOverlay:
    def __init__(self, master):
        self.master = master
        self.frame = tk.Frame(master, bg="#000000")
        self.box = tk.Frame(self.frame, bg="white", bd=2, relief="solid")
        self.label = tk.Label(self.box, text="CONNECTING...\nPlease wait", font=("Arial", 14), bg="white")
    def show(self):
        self.frame.place(x=0, y=0, width=DISPLAY_W, height=DISPLAY_H)
        bw, bh = DISPLAY_W//2, 70
        x = (DISPLAY_W - bw)//2
        y = (DISPLAY_H - bh)//2
        self.box.place(x=x, y=y, width=bw, height=bh)
        self.label.pack(expand=True)
        self.frame.lift()
    def hide(self):
        try:
            self.label.pack_forget()
            self.box.place_forget()
            self.frame.place_forget()
        except:
            pass

class FullKeyboardFrame(tk.Frame):
    def __init__(self, master, on_connect, on_back, **kwargs):
        super().__init__(master, bg="white", **kwargs)
        self.on_connect = on_connect
        self.on_back = on_back
        self.shift = False
        self.one_shot = True
        self.mode = "abc"
        self.var = tk.StringVar(value="")
        self.visible = tk.BooleanVar(value=False)
        self.build()

    def build(self):
        for w in self.winfo_children():
            w.destroy()

        top = tk.Frame(self, bg="white")
        top.pack(fill="x", pady=(24,8))  # Large margin for visual clarity

        entry = tk.Entry(top, textvariable=self.var, font=("Arial", 24, "bold"), bd=2, relief="solid", justify="center")
        entry.pack(fill="x", padx=24, ipady=18)
        entry.config(show="â€¢" if not self.visible.get() else "")

        show_pw_button = tk.Checkbutton(self,
            text="Show password",
            variable=self.visible,
            command=self.toggle_visible,
            font=("Arial", 18, "bold"),
            bg="white",
            indicatoron=False,
            bd=2, relief="raised",
            width=18, height=2,
            pady=10
        )
        show_pw_button.pack(fill="x", padx=60, pady=(6, 18))

        mode_row = tk.Frame(self, bg="white")
        mode_row.pack(fill="x", pady=(2,18))
        modes = [("ABC", "abc"), ("123", "num"), ("SYM", "sym")]
        for name, key in modes:
            f = "#1f8a50" if self.mode == key else DEFAULT_BUTTON_BG
            fg = "white" if self.mode == key else "black"
            b = tk.Button(mode_row, text=name, font=("Arial", 20, "bold"), bg=f, fg=fg,
                          command=lambda k=key: self.set_mode(k), height=2, width=10)
            b.pack(side="left", expand=True, fill="both", padx=10, ipadx=18, ipady=12)

        key_area = tk.Frame(self, bg="white")
        key_area.pack(expand=True, fill="both", pady=(0, 16))

        if self.mode == "abc":
            self.build_abc_keyboard(key_area)
        elif self.mode == "num":
            self.build_num_keyboard(key_area)
        elif self.mode == "sym":
            self.build_sym_keyboard(key_area)

        ctrl = tk.Frame(self, bg="white")
        ctrl.pack(fill="x", pady=12)
        if self.mode == "abc":
            self.shift_btn = tk.Button(ctrl, text="SHIFT", font=KEYBOARD_FONT, command=self.toggle_shift, height=2, width=9)
            self.shift_btn.pack(side="left", padx=10, ipadx=22, ipady=8)
        space = tk.Button(ctrl, text="SPACE", font=KEYBOARD_FONT, command=lambda: self.key(" "), height=2, width=18)
        space.pack(side="left", padx=10, ipadx=48, ipady=8, expand=True, fill="x")
        back = tk.Button(ctrl, text="BACK", font=KEYBOARD_FONT, command=self.do_back, height=2, width=10)
        back.pack(side="left", padx=10, ipadx=22, ipady=8)
        ok = tk.Button(ctrl, text="CONNECT", font=KEYBOARD_FONT, bg="#1f8a50", fg="white", command=self.do_connect, height=2, width=13)
        ok.pack(side="left", padx=10, ipadx=32, ipady=8)

    def set_mode(self, mode):
        self.mode = mode
        self.shift = False
        self.build()

    def build_abc_keyboard(self, frame):
        self.alpha_buttons = []
        rows = [list("qwertyuiop"), list("asdfghjkl"), list("zxcvbnm")]
        for rkeys in rows:
            rf = tk.Frame(frame, bg="white")
            rf.pack(expand=True, fill="both", pady=4)
            for k in rkeys:
                display_k = k.upper() if self.shift else k.lower()
                b = tk.Button(rf, text=display_k, font=KEYBOARD_FONT, bg=DEFAULT_BUTTON_BG,
                              command=lambda ch=display_k: self.key(ch), height=2, width=3)
                b.pack(side="left", expand=True, fill="both", padx=4, pady=2)
                self.alpha_buttons.append(b)

    def build_num_keyboard(self, frame):
        num_row = tk.Frame(frame, bg="white")
        num_row.pack(expand=True, fill="both")
        for d in list("1234567890"):
            b = tk.Button(num_row, text=d, font=KEYBOARD_FONT, bg=DEFAULT_BUTTON_BG,
                          command=lambda ch=d: self.key(ch), height=4, width=6)
            b.pack(side="left", expand=True, fill="both", padx=4, pady=12)

    def build_sym_keyboard(self, frame):
        sym_list = list("!@#$%^&*()_+-=[]{};:'\",.<>/?\\|")
        row_len = 10
        for i in range(0, len(sym_list), row_len):
            rf = tk.Frame(frame, bg="white")
            rf.pack(expand=True, fill="both", pady=4)
            for s in sym_list[i:i+row_len]:
                b = tk.Button(rf, text=s, font=KEYBOARD_FONT, bg=DEFAULT_BUTTON_BG,
                              command=lambda ch=s: self.key(ch), height=2, width=3)
                b.pack(side="left", expand=True, fill="both", padx=3, pady=2)

    def toggle_visible(self):
        self.build()

    def toggle_shift(self):
        self.shift = not self.shift
        self.build()

    def key(self, ch):
        self.var.set(self.var.get() + ch)
    def do_back(self):
        if callable(self.on_back):
            self.on_back()
    def do_connect(self):
        val = self.var.get()
        if callable(self.on_connect):
            self.on_connect(val)

class WifiKiosk:
    def __init__(self, root):
        self.root = root
        self.selected_ssid = None
        self.selected_security = None
        self.password = None
        # Header/info, only used in Wi-Fi list mode:
        self.header = tk.Frame(root, bg="white")
        self.header.pack(fill="x", pady=4)
        tk.Label(self.header, text="Select Wi-Fi Network", font=("Arial",18,"bold"), bg="white").pack(side="left", padx=8)
        tk.Button(self.header, text="CLOSE", font=("Arial",14), bg="#8a2b2b", fg="white", command=self.close).pack(side="right", padx=8)
        self.status_var = tk.StringVar(value="Scanning networks...")
        self.status_label = tk.Label(root, textvariable=self.status_var, font=("Arial",14), bg="white")
        self.status_label.pack(fill="x")

        self.list_frame = tk.Frame(root, bg="white")
        self.list_frame.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(self.list_frame, bg="white", highlightthickness=0, width=DISPLAY_W-20)
        self.scroll = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg="white")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.bottom = tk.Frame(root, bg="white")
        self.bottom.pack(fill="x", pady=4)
        tk.Button(self.bottom, text="REFRESH", font=("Arial", 14), command=self.force_refresh).pack(side="left", padx=6)
        tk.Button(self.bottom, text="â–² UP", font=("Arial", 14), command=lambda: self.canvas.yview_scroll(-3, "units")).pack(side="left", padx=6)
        tk.Button(self.bottom, text="â–¼ DOWN", font=("Arial", 14), command=lambda: self.canvas.yview_scroll(3, "units")).pack(side="left", padx=6)
        tk.Label(self.bottom, text="Selecting & connecting will enable autoconnect on boot.", font=("Arial",12), bg="white").pack(side="right", padx=6)

        self.keyboard_frame = FullKeyboardFrame(root, on_connect=self.on_keyboard_connect, on_back=self.hide_keyboard)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag_move)
        self._drag_y = None
        self.overlay = ConnectingOverlay(root)
        self.refreshing = False
        self.stop_flag = False
        self.scan_and_show()

    def _on_mousewheel(self, e):
        if getattr(e, "num", None) == 5 or getattr(e, "delta", 0) == -120:
            self.canvas.yview_scroll(1, "units")
        elif getattr(e, "num", None) == 4 or getattr(e, "delta", 0) == 120:
            self.canvas.yview_scroll(-1, "units")
        else:
            if hasattr(e, "delta"):
                self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")
    def _drag_start(self, e):
        if e.widget == self.canvas:
            self._drag_y = e.y_root
    def _drag_move(self, e):
        if self._drag_y is None:
            return
        dy = e.y_root - self._drag_y
        self.canvas.yview_scroll(int(-dy/30), "units")
        self._drag_y = e.y_root
    def force_refresh(self):
        if not self.refreshing:
            self.scan_and_show(force=True)
    def scan_and_show(self, force=False):
        if self.refreshing and not force:
            return
        self.refreshing = True
        self.status_var.set("Scanning networks...")
        def worker():
            nets = scan_wifi_once()
            self.root.after(0, lambda: self.show_networks(nets))
            self.refreshing = False
            if not self.stop_flag:
                self.root.after(REFRESH_INTERVAL * 1000, self.scan_and_show)
        bg_thread(worker)
    def show_networks(self, nets):
        for w in self.inner.winfo_children():
            w.destroy()
        if not nets:
            tk.Label(self.inner, text="No networks found. Enable Wi-Fi.", font=LIST_FONT, bg="white").pack(pady=6)
            self.status_var.set("No networks.")
            return
        active = get_active_ssid()
        if active:
            self.status_var.set(f"Connected: {active}")
        else:
            self.status_var.set(f"Found {len(nets)} networks. Tap to connect.")
        for n in nets:
            ssid = n["ssid"]
            sec = n["security"]
            sig = n["signal"]
            sec_text = "Open" if (sec == "" or sec.lower() in ("--","none")) else "Secured"
            disp = f"{ssid}   [{sec_text}]   ({sig}%)"
            btn = tk.Button(
                self.inner,
                text=disp,
                font=LIST_FONT,
                anchor="w",
                height=3,
                wraplength=DISPLAY_W-40,
                bg=DEFAULT_BUTTON_BG,
                command=lambda s=ssid, se=sec: self.on_select(s, se)
            )
            btn.pack(fill="x", padx=12, pady=10)
    def on_select(self, ssid, security):
        self.selected_ssid = ssid
        self.selected_security = security
        sec = security.lower()
        secured = not (sec == "" or sec == "--" or sec == "none")
        if secured:
            self.show_keyboard_for(ssid)
        else:
            self.password = ""
            self.status_var.set(f"Connecting to {ssid} ...")
            self.connect(ssid, "")
    def show_keyboard_for(self, ssid):
        self.status_var.set(f"Enter password for {ssid}")
        self.header.pack_forget()       # Hide info header
        self.status_label.pack_forget() # Hide status label
        self.list_frame.pack_forget()   # Hide Wi-Fi list
        self.bottom.pack_forget()       # Hide bottom controls
        self.keyboard_frame.var.set("")
        self.keyboard_frame.visible.set(False)
        self.keyboard_frame.set_mode("abc")
        self.keyboard_frame.pack(fill="both", expand=True)
        # Select entry for focus
        for w in self.keyboard_frame.winfo_children():
            if isinstance(w, tk.Frame):
                for c in w.winfo_children():
                    if isinstance(c, tk.Entry):
                        c.focus_set()
                        break
    def hide_keyboard(self):
        self.keyboard_frame.pack_forget()
        self.header.pack(fill="x", pady=4)
        self.status_label.pack(fill="x")
        self.list_frame.pack(fill="both", expand=True)
        self.bottom.pack(fill="x", pady=4)
        self.keyboard_frame.var.set("")
        self.canvas.yview_moveto(0)
    def on_keyboard_connect(self, password):
        ssid = self.selected_ssid
        self.password = password or ""
        self.status_var.set(f"Connecting to {ssid} ...")
        self.keyboard_frame.pack_forget()
        self.header.pack(fill="x", pady=4)
        self.status_label.pack(fill="x")
        self.list_frame.pack(fill="both", expand=True)
        self.bottom.pack(fill="x", pady=4)
        self.connect(ssid, self.password)
    def connect(self, ssid, password):
        def worker():
            self.root.after(0, self.overlay.show)
            if password == "":
                cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
            else:
                cmd = ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
            rc, out, err = run_cmd(cmd, timeout=35)
            self.root.after(0, self.overlay.hide)
            if rc == 0:
                time.sleep(0.3)
                run_cmd(['nmcli', 'connection', 'modify', ssid, 'connection.autoconnect', 'yes'])
                self.root.after(0, lambda: self.on_connect_success(ssid))
            else:
                msg = err if err else out if out else "Unknown"
                self.root.after(0, lambda: self.on_connect_failure(ssid, msg))
        bg_thread(worker)
    def on_connect_success(self, ssid):
        self.status_var.set(f"Connected to {ssid}.")
        self.root.after(900, lambda: self.close())
    def on_connect_failure(self, ssid, msg):
        self.status_var.set(f"Failed to connect: {msg}")
        self.root.after(1400, lambda: self.scan_and_show(force=True))
    def close(self):
        self.stop_flag = True
        try:
            self.root.destroy()
        except:
            pass

def main():
    rc, out, err = run_cmd("which nmcli")
    if rc != 0 or not out:
        print("nmcli not found. Install NetworkManager or ask for wpa_supplicant variant.")
        sys.exit(1)

    root = tk.Tk()
    screen_w = root.winfo_screenwidth()
    screen_h = root.winfo_screenheight()
    global DISPLAY_W, DISPLAY_H
    DISPLAY_W, DISPLAY_H = screen_w, screen_h
    root.geometry(f"{DISPLAY_W}x{DISPLAY_H}+0+0")
    root.attributes("-fullscreen", True)
    root.overrideredirect(True)
    root.lift()
    root.update()
    root.focus_force()
    root.configure(bg="white")

    app = WifiKiosk(root)
    root.mainloop()

if __name__ == "__main__":
    main()
