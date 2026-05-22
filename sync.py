import sys
import json
import os
import threading
import importlib
import requests
import pyodbc
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import pystray
from PIL import Image
import ctypes
import ctypes.wintypes

from acc_productproduct_sync import run_sync as sync_acc_productproduct
from acc_productbrand_sync import run_sync as sync_acc_productbrand
from acc_master_sync import run_sync as sync_acc_master
from acc_product_sync import run_sync as sync_acc_product
from acc_productbatch_sync import run_sync as sync_acc_productbatch
from acc_productphoto_sync import run_sync as sync_acc_productphoto
from acc_users_sync import run_sync as sync_acc_users
from acc_servicemaster_sync import run_sync as sync_acc_servicemaster

SYNCS = [
    ("acc_productproduct", sync_acc_productproduct),
    ("acc_productbrand",   sync_acc_productbrand),
    ("acc_master",         sync_acc_master),
    ("acc_product",        sync_acc_product),
    ("acc_productbatch",   sync_acc_productbatch),
    ("acc_productphoto",   sync_acc_productphoto),
    ("acc_users",          sync_acc_users),
    ("acc_servicemaster",  sync_acc_servicemaster),
]

DISPLAY_NAMES = {
    "acc_productproduct": "Products",
    "acc_productbrand":   "Brands",
    "acc_master":         "Customers",
    "acc_product":        "Items",
    "acc_productbatch":   "Barcodes",
    "acc_productphoto":   "Photos",
    "acc_users":          "Users",
    "acc_servicemaster":  "Service Sections",
}

BASE_URL    = "https://pkb2bsyncapi.myimc.in/api"
SQL_USERNAME = "dba"
SQL_PASSWORD = "(*$^)"

BG      = "#1e1e2e"
BG2     = "#181825"
FG      = "#cdd6f4"
FG_DIM  = "#6c7086"
GREEN   = "#a6e3a1"
RED     = "#f38ba8"
YELLOW  = "#f9e2af"
BLUE    = "#89b4fa"
SURFACE = "#313244"


def load_config():
    base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, 'config.json')) as f:
        return json.load(f)


def check_odbc_connection():
    try:
        cfg = load_config()
        conn = pyodbc.connect(f"DSN={cfg['dsn']};UID=dba;PWD=(*$^)", timeout=3)
        conn.close()
        return True, cfg["dsn"]
    except Exception as e:
        return False, str(e)


def check_api_connection():
    try:
        response = requests.get(BASE_URL.replace("/api", ""), timeout=5)
        return True
    except Exception:
        return False


class SyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PKB2B Sync Tool")
        self.root.geometry("700x650")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self._stop_flag = False
        self._auto_sync_job = None
        self._countdown_job = None
        self._countdown_secs = 0
        self._auto_start = True
        cfg = load_config()
        self._auto_sync_mins = int(cfg.get("auto_sync_minutes", 0))
        self._build_ui()
        self._check_connections()

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(18, 4))

        tk.Label(hdr, text="PKB2B Sync Tool", font=("Segoe UI", 15, "bold"),
                 bg=BG, fg=FG).pack(side="left")

        self.clock_lbl = tk.Label(hdr, text="", font=("Segoe UI", 9),
                                  bg=BG, fg=FG_DIM)
        self.clock_lbl.pack(side="right")
        self._tick()

        tk.Label(self.root, text="SQL Anywhere  →  PostgreSQL",
                 font=("Segoe UI", 9), bg=BG, fg=FG_DIM).pack(anchor="w", padx=24)

        ttk.Separator(self.root).pack(fill="x", padx=24, pady=10)

        # ── Connection Status Panel ──────────────────────────────
        conn_frame = tk.Frame(self.root, bg=SURFACE, pady=10)
        conn_frame.pack(fill="x", padx=24, pady=(0, 10))

        tk.Label(conn_frame, text="  Connection Status",
                 font=("Segoe UI", 9, "bold"), bg=SURFACE, fg=FG).pack(anchor="w", padx=10)

        row = tk.Frame(conn_frame, bg=SURFACE)
        row.pack(fill="x", padx=10, pady=(6, 2))

        # SQL Anywhere status
        sql_col = tk.Frame(row, bg=SURFACE)
        sql_col.pack(side="left", expand=True, fill="x")
        tk.Label(sql_col, text="ODBC (SQL Anywhere)", font=("Segoe UI", 8),
                 bg=SURFACE, fg=FG_DIM).pack(anchor="w")
        self.sql_dot = tk.Label(sql_col, text="● Checking...",
                                font=("Segoe UI", 9, "bold"), bg=SURFACE, fg=YELLOW)
        self.sql_dot.pack(anchor="w")

        # API server status
        api_col = tk.Frame(row, bg=SURFACE)
        api_col.pack(side="left", expand=True, fill="x")
        tk.Label(api_col, text="API Server", font=("Segoe UI", 8),
                 bg=SURFACE, fg=FG_DIM).pack(anchor="w")
        self.api_dot = tk.Label(api_col, text="● Checking...",
                                font=("Segoe UI", 9, "bold"), bg=SURFACE, fg=YELLOW)
        self.api_dot.pack(anchor="w")

        # refresh button
        tk.Button(conn_frame, text="↻ Refresh",
                  font=("Segoe UI", 8), bg=SURFACE, fg=FG_DIM,
                  relief="flat", cursor="hand2",
                  command=self._check_connections).pack(anchor="e", padx=10)

        # ── Table ───────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview",
                        background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=28,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
                        background=SURFACE, foreground=FG,
                        font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", SURFACE)])

        cols = ("table", "status", "total", "time")
        self.tree = ttk.Treeview(self.root, columns=cols,
                                 show="headings", height=len(SYNCS))

        widths = {"table": 250, "status": 120, "total": 120, "time": 150}
        heads  = {"table": "Table", "status": "Status",
                  "total": "Total", "time": "Duration"}

        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="center")
        self.tree.column("table", anchor="w")
        self.tree.pack(padx=24, pady=(0, 6))

        self.rows = {}
        for name, _ in SYNCS:
            iid = self.tree.insert("", "end", values=(DISPLAY_NAMES[name], "—", "—", "—"))
            self.rows[name] = iid

        # ── Progress bar ────────────────────────────────────────
        style.configure("Sync.Horizontal.TProgressbar",
                        troughcolor=BG2, background=BLUE, thickness=6)
        self.progress = ttk.Progressbar(self.root, style="Sync.Horizontal.TProgressbar",
                                        maximum=len(SYNCS), length=652)
        self.progress.pack(padx=24, pady=(4, 0))

        self.status_var = tk.StringVar(value="Ready to sync.")
        tk.Label(self.root, textvariable=self.status_var,
                 font=("Segoe UI", 9), bg=BG, fg=FG_DIM).pack(pady=(4, 0))

        ttk.Separator(self.root).pack(fill="x", padx=24, pady=10)

        # ── Buttons ─────────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack()

        self.start_btn = tk.Button(
            btn_frame, text="▶   Start Sync",
            font=("Segoe UI", 10, "bold"),
            bg=GREEN, fg=BG, activebackground="#94d3a2",
            relief="flat", padx=24, pady=9,
            cursor="hand2", command=self.start_sync)
        self.start_btn.pack(side="left", padx=10)

        self.stop_btn = tk.Button(
            btn_frame, text="■   End Sync",
            font=("Segoe UI", 10, "bold"),
            bg=RED, fg=BG, activebackground="#e37a97",
            relief="flat", padx=24, pady=9,
            cursor="hand2", state="disabled",
            command=self.end_sync)
        self.stop_btn.pack(side="left", padx=10)

        self.summary_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.summary_var,
                 font=("Segoe UI", 9, "bold"), bg=BG, fg=GREEN).pack(pady=(10, 0))

        self.auto_sync_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.auto_sync_var,
                 font=("Segoe UI", 9), bg=BG, fg=BLUE).pack(pady=(4, 0))

    # ── connection check ─────────────────────────────────────────
    def _check_connections(self):
        self.sql_dot.config(text="● Checking...", fg=YELLOW)
        self.api_dot.config(text="● Checking...", fg=YELLOW)
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self._do_check, daemon=True).start()

    def _do_check(self):
        sql_ok, sql_msg = check_odbc_connection()
        api_ok = check_api_connection()

        self.sql_dot.config(
            text=f"● Connected ({sql_msg})" if sql_ok else "● Disconnected",
            fg=GREEN if sql_ok else RED
        )
        self.api_dot.config(
            text="● Connected" if api_ok else "● Disconnected",
            fg=GREEN if api_ok else RED
        )

        if sql_ok and api_ok:
            self.start_btn.configure(state="normal")
            self.status_var.set("Ready to sync.")
            if self._auto_start:
                self._auto_start = False
                self.root.after(200, self.start_sync)
        else:
            self.start_btn.configure(state="disabled")
            self.status_var.set("Cannot sync: check connection status above.")

    # ── clock ────────────────────────────────────────────────────
    def _tick(self):
        self.clock_lbl.config(text=datetime.now().strftime("%d %b %Y  %H:%M:%S"))
        self.root.after(1000, self._tick)

    # ── table helpers ────────────────────────────────────────────
    def _set_row(self, name, status, total="—", dur="—"):
        colors = {"Syncing...": YELLOW, "Done": GREEN,
                  "Failed": RED, "Stopped": RED, "—": FG_DIM}
        self.tree.item(self.rows[name], values=(DISPLAY_NAMES[name], status, total, dur))
        tag = f"tag_{name}"
        self.tree.tag_configure(tag, foreground=colors.get(status, FG))
        self.tree.item(self.rows[name], tags=(tag,))

    def _reset_table(self):
        for name, _ in SYNCS:
            self._set_row(name, "—")
        self.progress["value"] = 0
        self.summary_var.set("")

    # ── sync control ─────────────────────────────────────────────
    def start_sync(self):
        self._stop_flag = False
        self._reset_table()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("Syncing...")
        threading.Thread(target=self._run_all, daemon=True).start()

    def end_sync(self):
        self._stop_flag = True
        self._cancel_auto_sync()

    def _cancel_auto_sync(self):
        if self._auto_sync_job:
            self.root.after_cancel(self._auto_sync_job)
            self._auto_sync_job = None
        if self._countdown_job:
            self.root.after_cancel(self._countdown_job)
            self._countdown_job = None
        self.auto_sync_var.set("")

    def _schedule_auto_sync(self):
        if self._auto_sync_mins <= 0:
            return
        self._countdown_secs = self._auto_sync_mins * 60
        self._tick_countdown()

    def _tick_countdown(self):
        if self._countdown_secs <= 0:
            self.auto_sync_var.set("")
            self.start_sync()
            return
        mins, secs = divmod(self._countdown_secs, 60)
        self.auto_sync_var.set(f"⏱  Next auto sync in {mins:02d}:{secs:02d}")
        self._countdown_secs -= 1
        self._countdown_job = self.root.after(1000, self._tick_countdown)

    # ── run all syncs ────────────────────────────────────────────
    def _run_all(self):
        total_synced = 0
        mod_map = {
            "acc_productproduct": "acc_productproduct_sync",
            "acc_productbrand":   "acc_productbrand_sync",
            "acc_master":         "acc_master_sync",
            "acc_product":        "acc_product_sync",
            "acc_productbatch":   "acc_productbatch_sync",
            "acc_productphoto":   "acc_productphoto_sync",
            "acc_users":          "acc_users_sync",
            "acc_servicemaster":  "acc_servicemaster_sync",
        }

        for idx, (name, fn) in enumerate(SYNCS):
            if self._stop_flag:
                self._set_row(name, "Stopped")
                self.status_var.set("Stopped by user.")
                break

            self._set_row(name, "Syncing...")
            self.status_var.set(f"Syncing  {name} ...")
            synced = 0
            t0 = datetime.now()
            mod = importlib.import_module(mod_map[name])

            class Null:
                def write(self, _): pass
                def flush(self): pass
            sys.stdout = Null()

            try:
                orig_push = mod.push_to_api
                cfg = mod.load_config()
                conn = mod.get_sql_connection(cfg)
                total = mod.get_total_count(conn)
                conn.close()
                self._set_row(name, "Syncing...", f"0/{total}")

                def patched_push(cfg, records, is_first_batch=False, _orig=orig_push):
                    nonlocal synced
                    result = _orig(cfg, records, is_first_batch)
                    synced += result.get("synced", 0)
                    self._set_row(name, "Syncing...", f"{synced}/{total}")
                    self.status_var.set(f"Syncing {name} ... {synced}/{total}")
                    return result

                mod.push_to_api = patched_push
                fn()
                mod.push_to_api = orig_push
                sys.stdout = sys.__stdout__

                dur = f"{(datetime.now() - t0).seconds}s"
                self._set_row(name, "Done", f"{synced}/{total}", dur)
                total_synced += synced

            except Exception as e:
                sys.stdout = sys.__stdout__
                mod.push_to_api = orig_push
                self._set_row(name, "Failed", "—", "—")
                self.status_var.set(f"Error in {name}: {e}")
                import traceback; traceback.print_exc()

            self.progress["value"] = idx + 1

        if not self._stop_flag:
            self.status_var.set("All syncs completed.")
            self.summary_var.set("✓  All syncs completed successfully.")
            self._schedule_auto_sync()

        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")


def _make_tray_image():
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    ico = os.path.join(base, "pk.png")
    if os.path.exists(ico):
        return Image.open(ico).convert("RGBA").resize((64, 64))
    img = Image.new("RGBA", (64, 64), (137, 180, 250, 255))
    return img


if __name__ == "__main__":
    # ── Single instance check ────────────────────────────────────
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "PKB2B_Sync_Mutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        ctypes.windll.user32.MessageBoxW(
            None,
            "PKB2B Sync Tool is already running.\nCheck the system tray.",
            "Already Running",
            0x40 | 0x1000  # MB_ICONINFORMATION | MB_SYSTEMMODAL
        )
        sys.exit(0)

    root = tk.Tk()
    root.withdraw()
    app = SyncApp(root)

    def show_window(icon=None, item=None):
        root.deiconify()
        root.state("normal")
        root.lift()
        root.focus()

    def quit_app(icon, item):
        icon.stop()
        root.destroy()

    tray_icon = pystray.Icon(
        "PKB2B_Sync",
        _make_tray_image(),
        "PKB2B Sync Tool",
        menu=pystray.Menu(
            pystray.MenuItem("Show", show_window, default=True),
            pystray.MenuItem("Exit", quit_app),
        )
    )

    root.protocol("WM_DELETE_WINDOW", lambda: (root.state("normal"), root.withdraw()))

    threading.Thread(target=tray_icon.run, daemon=True).start()
    root.mainloop()