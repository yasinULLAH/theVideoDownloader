import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import yt_dlp
import threading
import os, sys, subprocess, queue, shutil, time, datetime, platform, re, json

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_TITLE  = "YD — Video Downloader"
AUTHOR     = "yasin ullah"
APP_SIZE   = "980x720"
HISTORY_FILE = os.path.join(os.getcwd(), "download_history.json")

# ── colour palette ────────────────────────────────────────────────────────────
C = {
    "bg":      "#0f0f0f",
    "surface": "#181818",
    "card":    "#212121",
    "border":  "#2c2c2c",
    "accent":  "#6c63ff",
    "accent2": "#5a52e0",
    "green":   "#22c55e",
    "red":     "#ef4444",
    "amber":   "#f59e0b",
    "text":    "#f1f1f1",
    "muted":   "#6b7280",
    "white":   "#ffffff",
}

FONT_HEAD  = ("Inter", 14, "bold")
FONT_BODY  = ("Inter", 11)
FONT_SMALL = ("Inter", 10)
FONT_MONO  = ("Consolas", 10)

# ── logger ────────────────────────────────────────────────────────────────────
class _Logger:
    def __init__(self, q): self.q = q
    def debug(self, m):
        if not m.startswith("[debug]"): self.q.put(("log", m))
    def info(self, m):    self.q.put(("log", m))
    def warning(self, m): self.q.put(("log", f"⚠ {m}"))
    def error(self, m):   self.q.put(("log", f"✖ {m}"))

# ── slim progress bar ─────────────────────────────────────────────────────────
class SlimBar(tk.Canvas):
    def __init__(self, parent, h=4, color=C["accent"]):
        super().__init__(parent, height=h, bg=C["surface"], highlightthickness=0)
        self._color = color; self._val = 0.0; self._width_val = 0; self._h = h
        self._bar = self.create_rectangle(0, 0, 0, h, fill=color, width=0)
        self.bind("<Configure>", lambda e: setattr(self, "_width_val", e.width) or self._draw())

    def set(self, v):
        self._val = max(0.0, min(1.0, float(v))); self._draw()

    def _draw(self):
        if self._width_val: self.coords(self._bar, 0, 0, self._width_val * self._val, self._h)

# ── batch item row ────────────────────────────────────────────────────────────
class BatchRow(ctk.CTkFrame):
    def __init__(self, parent, url, on_remove):
        super().__init__(parent, fg_color=C["card"], corner_radius=8)
        self.url = url
        self.pack(fill="x", pady=3, padx=6)
        self._icon = ctk.CTkLabel(self, text="⏳", width=28, font=("Inter",13), text_color=C["muted"])
        self._icon.pack(side="left", padx=(10,4))
        disp = url if len(url) < 62 else url[:59]+"…"
        ctk.CTkLabel(self, text=disp, font=FONT_SMALL, text_color=C["text"], anchor="w").pack(side="left", fill="x", expand=True)
        self._info = ctk.CTkLabel(self, text="", width=160, font=FONT_SMALL, text_color=C["muted"])
        self._info.pack(side="left", padx=6)
        self._bar = SlimBar(self, h=3, color=C["accent"])
        self._bar.place(relx=0, rely=1.0, relwidth=1.0, anchor="sw", y=-1)
        self.configure(height=40)
        ctk.CTkButton(self, text="✕", width=26, height=26, fg_color="transparent",
                      hover_color=C["border"], text_color=C["muted"],
                      command=lambda: on_remove(self)).pack(side="right", padx=6)

    def update_progress(self, pct, info=""):
        self._bar.set(pct)
        self._info.configure(text=info)
        if pct >= 1.0:
            self._icon.configure(text="✔", text_color=C["green"])
        elif pct > 0:
            self._icon.configure(text="↓", text_color=C["accent"])

    def set_error(self): self._icon.configure(text="✖", text_color=C["red"])
    def set_cancelled(self): self._icon.configure(text="–", text_color=C["muted"])

# ── main app ──────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry(APP_SIZE)
        root.resizable(True, True)
        root.configure(bg=C["bg"])
        os.environ["PATH"] += os.pathsep + os.getcwd()

        self.has_ffmpeg    = shutil.which("ffmpeg") is not None
        self.gui_q         = queue.Queue()
        self.is_dl         = False
        self.is_paused     = False
        self.cancel_flag   = False
        self.last_clip     = ""
        self.fetch_thread  = None
        self.batch_rows    = []
        self.history       = self._load_history()

        self._build_ui()
        self._poll()
        self._start_clipboard()
        self.log(f"Ready — FFmpeg: {'✔' if self.has_ffmpeg else '✖ (safe mode)'}")

    # ── history helpers ───────────────────────────────────────────────────────
    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, encoding="utf-8") as f: return json.load(f)
            except: pass
        return []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(self.history, f, indent=2)
        except: pass

    def _add_history(self, url, title=""):
        entry = {"ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "url": url, "title": title}
        self.history.insert(0, entry)
        self.history = self.history[:300]
        self._save_history()
        self.gui_q.put(("history_refresh",))

    # ── UI build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        hdr = ctk.CTkFrame(self.root, fg_color=C["surface"], height=52, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="YD", font=("Inter",18,"bold"), text_color=C["accent"]).pack(side="left", padx=18)
        ctk.CTkLabel(hdr, text="Video Downloader", font=("Inter",13), text_color=C["muted"]).pack(side="left")
        ctk.CTkLabel(hdr, text=f"by {AUTHOR}", font=FONT_SMALL, text_color=C["border"]).pack(side="right", padx=16)
        self.lbl_status = ctk.CTkLabel(hdr, text="● Ready", font=FONT_SMALL, text_color=C["green"])
        self.lbl_status.pack(side="right", padx=10)

        tab_style = dict(fg_color=C["bg"], segmented_button_fg_color=C["surface"],
                         segmented_button_selected_color=C["accent"],
                         segmented_button_selected_hover_color=C["accent2"],
                         segmented_button_unselected_color=C["surface"],
                         segmented_button_unselected_hover_color=C["border"],
                         text_color=C["text"])
        self.tabs = ctk.CTkTabview(self.root, **tab_style)
        self.tabs.pack(fill="both", expand=True, padx=0, pady=0)

        for name in ("  Download  ", "  Queue  ", "  History  ", "  Settings  "):
            self.tabs.add(name)

        self._build_download_tab(self.tabs.tab("  Download  "))
        self._build_batch_tab   (self.tabs.tab("  Queue  "))
        self._build_history_tab (self.tabs.tab("  History  "))
        self._build_settings_tab(self.tabs.tab("  Settings  "))

        self._log_visible = False
        self.log_frame = ctk.CTkFrame(self.root, fg_color="#0a0a0a", corner_radius=0, height=130)
        self.log_box   = ctk.CTkTextbox(self.log_frame, fg_color="#0a0a0a", text_color="#4ade80",
                                        font=FONT_MONO, border_width=0, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=8, pady=4)

        foot = ctk.CTkFrame(self.root, fg_color=C["surface"], height=32, corner_radius=0)
        foot.pack(fill="x", side="bottom")
        ctk.CTkButton(foot, text="Console", width=72, height=22, fg_color="transparent",
                      hover_color=C["border"], text_color=C["muted"], font=FONT_SMALL,
                      command=self._toggle_log).pack(side="right", padx=8, pady=4)

    # ── Download tab ──────────────────────────────────────────────────────────
    def _build_download_tab(self, tab):
        tab.configure(fg_color=C["bg"])
        wrap = ctk.CTkFrame(tab, fg_color=C["bg"])
        wrap.pack(fill="both", expand=True, padx=24, pady=16)

        url_card = ctk.CTkFrame(wrap, fg_color=C["surface"], corner_radius=12)
        url_card.pack(fill="x", pady=(0,12))
        url_inner = ctk.CTkFrame(url_card, fg_color="transparent")
        url_inner.pack(fill="x", padx=16, pady=14)

        self.entry_url = ctk.CTkEntry(url_inner, placeholder_text="Paste video URL…",
                                      height=40, font=("Inter",12), fg_color=C["card"],
                                      border_color=C["border"], border_width=1, corner_radius=8)
        self.entry_url.pack(side="left", fill="x", expand=True)
        self.entry_url.bind("<Return>", lambda _: self._fetch_meta())

        ctk.CTkButton(url_inner, text="Fetch", width=72, height=40, font=FONT_BODY,
                      fg_color=C["card"], hover_color=C["border"], border_color=C["border"],
                      border_width=1, corner_radius=8, command=self._fetch_meta).pack(side="left", padx=(8,0))
        ctk.CTkButton(url_inner, text="Paste", width=62, height=40, font=FONT_BODY,
                      fg_color=C["accent"], hover_color=C["accent2"], corner_radius=8,
                      command=self._paste).pack(side="left", padx=(6,0))

        self.meta_card = ctk.CTkFrame(wrap, fg_color=C["surface"], corner_radius=12)
        self.meta_card.pack(fill="x", pady=(0,12))
        meta_inner = ctk.CTkFrame(self.meta_card, fg_color="transparent")
        meta_inner.pack(fill="x", padx=16, pady=12)
        self.lbl_meta_title = ctk.CTkLabel(meta_inner, text="No video loaded", font=FONT_HEAD,
                                            text_color=C["text"], anchor="w", wraplength=600)
        self.lbl_meta_title.pack(anchor="w")
        self.lbl_meta_sub   = ctk.CTkLabel(meta_inner, text="", font=FONT_SMALL, text_color=C["muted"], anchor="w")
        self.lbl_meta_sub.pack(anchor="w", pady=(2,0))

        opts_card = ctk.CTkFrame(wrap, fg_color=C["surface"], corner_radius=12)
        opts_card.pack(fill="x", pady=(0,12))
        opts_inner = ctk.CTkFrame(opts_card, fg_color="transparent")
        opts_inner.pack(fill="x", padx=16, pady=14)

        ctk.CTkLabel(opts_inner, text="Format", font=FONT_SMALL, text_color=C["muted"]).grid(row=0,column=0,sticky="w",pady=(0,4))
        self.var_fmt = ctk.StringVar(value="video")
        fmt_row = ctk.CTkFrame(opts_inner, fg_color="transparent")
        fmt_row.grid(row=1, column=0, sticky="w", padx=(0,24))
        for t,v in [("Video (MP4)","video"),("Audio (MP3)","audio")]:
            ctk.CTkRadioButton(fmt_row, text=t, variable=self.var_fmt, value=v,
                               font=FONT_BODY, text_color=C["text"],
                               fg_color=C["accent"]).pack(side="left", padx=(0,14))

        ctk.CTkLabel(opts_inner, text="Quality", font=FONT_SMALL, text_color=C["muted"]).grid(row=0,column=1,sticky="w",pady=(0,4),padx=(0,24))
        self.combo_quality = ctk.CTkComboBox(opts_inner, values=["Best Available","4K","1080p","720p","480p","360p"],
                                              width=150, height=36, font=FONT_BODY,
                                              fg_color=C["card"], border_color=C["border"],
                                              button_color=C["border"], dropdown_fg_color=C["card"])
        self.combo_quality.set("Best Available")
        self.combo_quality.grid(row=1, column=1, sticky="w", padx=(0,24))

        ctk.CTkLabel(opts_inner, text="Save to", font=FONT_SMALL, text_color=C["muted"]).grid(row=0,column=2,sticky="w",pady=(0,4))
        self.var_path = os.getcwd()
        folder_row = ctk.CTkFrame(opts_inner, fg_color="transparent")
        folder_row.grid(row=1, column=2, sticky="ew")
        self.lbl_path = ctk.CTkLabel(folder_row, text=self._trunc(self.var_path),
                                      font=FONT_SMALL, text_color=C["muted"], anchor="w")
        self.lbl_path.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(folder_row, text="…", width=34, height=34, fg_color=C["card"],
                      hover_color=C["border"], corner_radius=6, command=self._browse).pack(side="left", padx=(6,0))
        ctk.CTkButton(folder_row, text="Open", width=50, height=34, fg_color=C["card"],
                      hover_color=C["border"], corner_radius=6, command=self._open_folder).pack(side="left", padx=(4,0))

        ctk.CTkLabel(opts_inner, text="Filename template", font=FONT_SMALL, text_color=C["muted"]).grid(row=2,column=0,sticky="w",pady=(10,4))
        self.entry_tmpl = ctk.CTkEntry(opts_inner, placeholder_text="%(title)s.%(ext)s",
                                        width=300, height=34, font=FONT_MONO,
                                        fg_color=C["card"], border_color=C["border"], border_width=1)
        self.entry_tmpl.insert(0, "%(title)s.%(ext)s")
        self.entry_tmpl.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0,2))
        ctk.CTkLabel(opts_inner, text="vars: %(upload_date)s  %(channel)s  %(id)s",
                      font=("Inter",9), text_color=C["muted"]).grid(row=4,column=0,columnspan=3,sticky="w")

        flags_row = ctk.CTkFrame(opts_inner, fg_color="transparent")
        flags_row.grid(row=5, column=0, columnspan=4, sticky="w", pady=(10,0))
        self.var_subs = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(flags_row, text="Embed Subtitles", variable=self.var_subs,
                         font=FONT_BODY, fg_color=C["accent"], text_color=C["text"]).pack(side="left", padx=(0,18))
        self.var_sponsor = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(flags_row, text="SponsorBlock (skip ads)", variable=self.var_sponsor,
                         font=FONT_BODY, fg_color=C["accent"], text_color=C["text"]).pack(side="left", padx=(0,18))
        self.var_thumb = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(flags_row, text="Embed Thumbnail", variable=self.var_thumb,
                         font=FONT_BODY, fg_color=C["accent"], text_color=C["text"]).pack(side="left")

        action_card = ctk.CTkFrame(wrap, fg_color=C["surface"], corner_radius=12)
        action_card.pack(fill="x", pady=(0,4))
        ac_inner = ctk.CTkFrame(action_card, fg_color="transparent")
        ac_inner.pack(fill="x", padx=16, pady=14)

        self.prog_bar = SlimBar(ac_inner, h=4, color=C["accent"])
        self.prog_bar.pack(fill="x", pady=(0,10))
        self.lbl_prog = ctk.CTkLabel(ac_inner, text="", font=FONT_SMALL, text_color=C["muted"], anchor="w")
        self.lbl_prog.pack(anchor="w", pady=(0,10))

        btn_row = ctk.CTkFrame(ac_inner, fg_color="transparent")
        btn_row.pack(fill="x")
        self.btn_start = ctk.CTkButton(btn_row, text="Start Download", height=44,
                                        font=("Inter",13,"bold"), fg_color=C["accent"],
                                        hover_color=C["accent2"], corner_radius=10,
                                        command=self._handle_start)
        self.btn_start.pack(side="left", fill="x", expand=True)
        self.btn_cancel = ctk.CTkButton(btn_row, text="Cancel", width=90, height=44,
                                         font=FONT_BODY, fg_color=C["card"],
                                         hover_color=C["border"], corner_radius=10,
                                         state="disabled", command=self._cancel)
        self.btn_cancel.pack(side="left", padx=(8,0))

    # ── Queue tab ─────────────────────────────────────────────────────────────
    def _build_batch_tab(self, tab):
        tab.configure(fg_color=C["bg"])
        top = ctk.CTkFrame(tab, fg_color=C["bg"])
        top.pack(fill="x", padx=24, pady=(16,8))
        ctk.CTkLabel(top, text="Download Queue", font=FONT_HEAD, text_color=C["text"]).pack(side="left")
        ctk.CTkButton(top, text="+ Add URLs", width=90, height=34, font=FONT_BODY,
                       fg_color=C["accent"], hover_color=C["accent2"], corner_radius=8,
                       command=self._batch_add_dialog).pack(side="right")
        ctk.CTkButton(top, text="Clear all", width=76, height=34, font=FONT_BODY,
                       fg_color=C["card"], hover_color=C["border"], corner_radius=8,
                       command=self._batch_clear).pack(side="right", padx=(0,8))

        self.batch_scroll = ctk.CTkScrollableFrame(tab, fg_color=C["bg"], corner_radius=0)
        self.batch_scroll.pack(fill="both", expand=True, padx=24, pady=(0,8))

        bot = ctk.CTkFrame(tab, fg_color=C["bg"])
        bot.pack(fill="x", padx=24, pady=(0,16))
        self.btn_batch_start = ctk.CTkButton(bot, text="Process Queue", height=42,
                                              font=("Inter",13,"bold"), fg_color=C["accent"],
                                              hover_color=C["accent2"], corner_radius=10,
                                              command=self._start_batch)
        self.btn_batch_start.pack(fill="x")

    # ── History tab ───────────────────────────────────────────────────────────
    def _build_history_tab(self, tab):
        tab.configure(fg_color=C["bg"])
        top = ctk.CTkFrame(tab, fg_color=C["bg"])
        top.pack(fill="x", padx=24, pady=(16,8))
        ctk.CTkLabel(top, text="Download History", font=FONT_HEAD, text_color=C["text"]).pack(side="left")
        ctk.CTkButton(top, text="Clear", width=62, height=32, font=FONT_SMALL,
                       fg_color=C["card"], hover_color=C["border"], corner_radius=8,
                       command=self._clear_history).pack(side="right")

        self.hist_scroll = ctk.CTkScrollableFrame(tab, fg_color=C["bg"], corner_radius=0)
        self.hist_scroll.pack(fill="both", expand=True, padx=24, pady=(0,16))
        self._render_history()

    def _render_history(self):
        for w in self.hist_scroll.winfo_children(): w.destroy()
        if not self.history:
            ctk.CTkLabel(self.hist_scroll, text="No downloads yet.", font=FONT_BODY,
                          text_color=C["muted"]).pack(pady=30)
            return
        for e in self.history:
            row = ctk.CTkFrame(self.hist_scroll, fg_color=C["surface"], corner_radius=8)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=e.get("ts", "Unknown Date"), font=FONT_SMALL, text_color=C["muted"], width=120).pack(side="left", padx=10)
            title = e.get("title") or e.get("url", "Unknown URL")
            disp  = title if len(title) < 64 else title[:61]+"…"
            ctk.CTkLabel(row, text=disp, font=FONT_SMALL, text_color=C["text"], anchor="w").pack(side="left", fill="x", expand=True)
            url = e.get("url", "")
            ctk.CTkButton(row, text="↓ Re-download", width=110, height=28, font=FONT_SMALL,
                            fg_color="transparent", hover_color=C["border"], text_color=C["accent"],
                            command=lambda u=url: self._redownload(u)).pack(side="right", padx=8, pady=6)

    def _clear_history(self):
        self.history = []; self._save_history(); self._render_history()

    def _redownload(self, url):
        self.entry_url.delete(0,"end"); self.entry_url.insert(0,url)
        self.tabs.set("  Download  ")

    # ── Settings tab ─────────────────────────────────────────────────────────
    def _build_settings_tab(self, tab):
        tab.configure(fg_color=C["bg"])
        wrap = ctk.CTkScrollableFrame(tab, fg_color=C["bg"], corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=24, pady=16)

        def section(title):
            ctk.CTkLabel(wrap, text=title, font=FONT_HEAD, text_color=C["text"]).pack(anchor="w", pady=(12,6))
            card = ctk.CTkFrame(wrap, fg_color=C["surface"], corner_radius=12)
            card.pack(fill="x")
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=12)
            return inner

        # General
        gen = section("General")
        self.var_clipboard = ctk.BooleanVar(value=True)
        self.var_playlist  = ctk.BooleanVar(value=False)
        for txt, var in [("Auto-paste links from clipboard", self.var_clipboard),
                          ("Create subfolder for playlists",  self.var_playlist)]:
            ctk.CTkCheckBox(gen, text=txt, variable=var, font=FONT_BODY,
                             text_color=C["text"], fg_color=C["accent"]).pack(anchor="w", pady=4)

        # Auth & Cookies
        auth = section("Authentication & Cookies")
        ctk.CTkLabel(auth, text="Cookies file (Netscape format):", font=FONT_SMALL, text_color=C["muted"]).pack(anchor="w")
        ck_row = ctk.CTkFrame(auth, fg_color="transparent")
        ck_row.pack(fill="x", pady=(4,8))
        self.entry_cookies = ctk.CTkEntry(ck_row, placeholder_text="Optional – path to cookies.txt",
                                           height=36, font=FONT_BODY, fg_color=C["card"],
                                           border_color=C["border"], border_width=1)
        self.entry_cookies.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(ck_row, text="Browse", width=70, height=36, fg_color=C["card"],
                       hover_color=C["border"], command=self._browse_cookies).pack(side="left", padx=(6,0))
        ctk.CTkLabel(auth, text="Browser (auto-extract cookies):", font=FONT_SMALL, text_color=C["muted"]).pack(anchor="w")
        self.combo_browser = ctk.CTkComboBox(auth, values=["None","chrome","firefox","edge","brave","safari"],
                                              width=160, height=34, font=FONT_BODY,
                                              fg_color=C["card"], border_color=C["border"],
                                              button_color=C["border"], dropdown_fg_color=C["card"])
        self.combo_browser.set("None")
        self.combo_browser.pack(anchor="w", pady=(4,0))

        # Network & Proxy
        net = section("Network & Proxy")
        for label, attr, ph in [
            ("Proxy URL:",    "entry_proxy", "e.g. socks5://127.0.0.1:1080"),
            ("User-Agent:",   "entry_ua",    "Leave blank for default"),
            ("Speed limit:",  "entry_speed", "e.g. 2M or 500K – blank = unlimited"),
        ]:
            r = ctk.CTkFrame(net, fg_color="transparent")
            r.pack(fill="x", pady=4)
            ctk.CTkLabel(r, text=label, font=FONT_SMALL, text_color=C["muted"], width=110, anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, placeholder_text=ph, height=34, font=FONT_BODY,
                              fg_color=C["card"], border_color=C["border"], border_width=1)
            e.pack(side="left", fill="x", expand=True)
            setattr(self, attr, e)

        # Audio ID3 Tags
        tags = section("Custom Audio ID3 Tags (MP3 only)")
        self._tag_fields = {}
        for label, key in [("Artist","artist"),("Album","album"),("Track Title","title")]:
            tr = ctk.CTkFrame(tags, fg_color="transparent")
            tr.pack(fill="x", pady=3)
            ctk.CTkLabel(tr, text=label+":", font=FONT_SMALL, text_color=C["muted"], width=90, anchor="w").pack(side="left")
            e = ctk.CTkEntry(tr, placeholder_text=f"Override {label.lower()} tag…",
                              height=32, font=FONT_BODY, fg_color=C["card"],
                              border_color=C["border"], border_width=1)
            e.pack(side="left", fill="x", expand=True)
            self._tag_fields[key] = e

        # System
        sys_sec = section("System")
        u_row = ctk.CTkFrame(sys_sec, fg_color="transparent")
        u_row.pack(fill="x")
        ctk.CTkLabel(u_row, text="yt-dlp library:", font=FONT_BODY, text_color=C["text"]).pack(side="left")
        ctk.CTkButton(u_row, text="Update now", width=100, height=32, font=FONT_SMALL,
                       fg_color=C["card"], hover_color=C["border"], corner_radius=8,
                       command=self._update_ytdlp).pack(side="right")

    # ── helpers ───────────────────────────────────────────────────────────────
    def _trunc(self, p, n=40): return ("…"+p[-(n-1):]) if len(p)>n else p

    def _paste(self):
        try:
            c = self.root.clipboard_get()
            self.entry_url.delete(0,"end"); self.entry_url.insert(0,c)
        except: pass

    def _browse(self):
        p = filedialog.askdirectory()
        if p: self.var_path = p; self.lbl_path.configure(text=self._trunc(p))

    def _browse_cookies(self):
        p = filedialog.askopenfilename(filetypes=[("Text","*.txt"),("All","*.*")])
        if p: self.entry_cookies.delete(0,"end"); self.entry_cookies.insert(0,p)

    def _open_folder(self):
        try:
            if platform.system()=="Windows": os.startfile(self.var_path)
            elif platform.system()=="Darwin": subprocess.Popen(["open",self.var_path])
            else: subprocess.Popen(["xdg-open",self.var_path])
        except Exception as e: messagebox.showerror("Error", str(e))

    def _toggle_log(self):
        if self._log_visible:
            self.log_frame.pack_forget(); self._log_visible=False
        else:
            self.log_frame.pack(fill="x", side="bottom", before=self.tabs)
            self._log_visible=True

    def log(self, msg): self.gui_q.put(("log", msg))

    def _set_status(self, text, color=C["muted"]):
        self.lbl_status.configure(text=text, text_color=color)

    # ── clipboard monitor ─────────────────────────────────────────────────────
    def _start_clipboard(self): self.root.after(1200, self._check_clip)

    def _check_clip(self):
        if self.var_clipboard.get():
            try:
                c = self.root.clipboard_get()
                if c != self.last_clip and any(x in c for x in ("youtube.com","youtu.be","vimeo.com","twitch.tv")):
                    self.last_clip = c
                    if not self.entry_url.get():
                        self.entry_url.insert(0, c)
            except: pass
        self.root.after(1500, self._check_clip)

    # ── metadata fetch ────────────────────────────────────────────────────────
    def _fetch_meta(self):
        url = self.entry_url.get().strip()
        if not url: return
        self.lbl_meta_title.configure(text="Fetching…")
        self.lbl_meta_sub.configure(text="")
        threading.Thread(target=self._fetch_meta_worker, args=(url,), daemon=True).start()

    def _fetch_meta_worker(self, url):
        try:
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True,"skip_download":True}) as ydl:
                info = ydl.extract_info(url, download=False)
            title   = info.get("title","Unknown")
            channel = info.get("channel") or info.get("uploader","")
            dur     = info.get("duration")
            dur_str = f"{int(dur)//60}:{int(dur)%60:02d}" if dur else "–"
            self.gui_q.put(("meta", title, f"{channel}  ·  {dur_str}"))
        except Exception as e:
            self.gui_q.put(("meta", "Could not fetch metadata", str(e)))

    # ── yt-dlp opts ───────────────────────────────────────────────────────────
    def _build_opts(self):
        fmt     = self.var_fmt.get()
        qual    = self.combo_quality.get()
        tmpl    = self.entry_tmpl.get().strip() or "%(title)s.%(ext)s"
        h_map   = {"4K":2160,"1080p":1080,"720p":720,"480p":480,"360p":360}
        limit   = h_map.get(qual)
        cookies = self.entry_cookies.get().strip()
        browser = self.combo_browser.get()
        proxy   = self.entry_proxy.get().strip()
        ua      = self.entry_ua.get().strip()
        speed   = self.entry_speed.get().strip()

        opts = {
            "logger": _Logger(self.gui_q),
            "progress_hooks": [self._progress_hook],
            "ignoreerrors": True,
            "writethumbnail": self.var_thumb.get(),
            "outtmpl": os.path.join(self.var_path, tmpl),
        }

        if self.var_playlist.get():
            opts["outtmpl"] = os.path.join(self.var_path, "%(playlist_title)s", "%(playlist_index)s - "+tmpl)
            opts["yes_playlist"] = True
        else:
            opts["noplaylist"] = True

        if cookies:          opts["cookiefile"] = cookies
        if browser != "None": opts["cookiesfrombrowser"] = (browser,)
        if proxy:            opts["proxy"] = proxy
        if ua:               opts["http_headers"] = {"User-Agent": ua}
        if speed:            opts["ratelimit"] = speed

        post = []
        if fmt == "audio":
            if self.has_ffmpeg:
                opts["format"] = "bestaudio/best"
                post.append({"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"})
                if self.var_thumb.get(): post.append({"key":"EmbedThumbnail"})
                meta_args = []
                for k, e in self._tag_fields.items():
                    v = e.get().strip()
                    if v: meta_args += ["-metadata", f"{k}={v}"]
                if meta_args:
                    post.append({"key":"FFmpegMetadata","add_metadata":True})
                    opts["postprocessor_args"] = meta_args
            else:
                opts["format"] = "bestaudio/best"
        else:
            if self.has_ffmpeg:
                opts["format"] = (f"bestvideo[height<={limit}]+bestaudio/best[height<={limit}]"
                                  if limit else "bestvideo+bestaudio/best")
                opts["merge_output_format"] = "mp4"
                if self.var_thumb.get(): post.append({"key":"EmbedThumbnail"})
            else:
                opts["format"] = (f"best[height<={limit}][ext=mp4]/best[ext=mp4]/best"
                                  if limit else "best[ext=mp4]/best")

        if self.var_subs.get() and self.has_ffmpeg:
            opts["writesubtitles"]    = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"]    = ["en"]
            post.append({"key":"FFmpegEmbedSubtitle"})

        if self.var_sponsor.get():
            opts["sponsorblock_mark"]   = ["sponsor"]
            opts["sponsorblock_remove"] = ["sponsor"]

        if post: opts["postprocessors"] = post
        return opts

    # ── progress hook ─────────────────────────────────────────────────────────
    def _progress_hook(self, d):
        if self.cancel_flag: raise Exception("Cancelled")
        while self.is_paused:
            time.sleep(0.4)
            if self.cancel_flag: raise Exception("Cancelled")
        if d["status"] == "downloading":
            try:
                p   = re.sub(r"\x1b\[[0-9;]*m","",d.get("_percent_str","0%")).replace("%","").strip()
                spd = re.sub(r"\x1b\[[0-9;]*m","",d.get("_speed_str","")).strip()
                eta = re.sub(r"\x1b\[[0-9;]*m","",d.get("_eta_str","")).strip()
                self.gui_q.put(("progress", float(p)/100, f"{p}%  ·  {spd}  ·  ETA {eta}",
                                d.get("_filename","")))
            except: pass
        elif d["status"] == "finished":
            self.gui_q.put(("progress", 1.0, "Finalising…", d.get("filename","")))

    # ── download workers ──────────────────────────────────────────────────────
    def _handle_start(self):
        if self.is_dl:
            if not self.is_paused:
                self.is_paused = True
                self.btn_start.configure(text="Resume", fg_color=C["amber"])
                self._set_status("● Paused", C["amber"])
            else:
                self.is_paused = False
                self.btn_start.configure(text="Pause", fg_color=C["amber"])
                self._set_status("● Downloading…", C["accent"])
            return
        url = self.entry_url.get().strip()
        if not url: return
        self._start_dl([url])

    def _cancel(self):
        self.cancel_flag = True
        self.is_paused   = False
        self.btn_cancel.configure(state="disabled", text="Stopping…")
        self._set_status("● Cancelling…", C["amber"])

    def _start_dl(self, urls):
        self.is_dl = True; self.is_paused = False; self.cancel_flag = False
        self.btn_start.configure(text="Pause", fg_color=C["amber"], state="normal")
        self.btn_cancel.configure(state="normal", text="Cancel")
        self.btn_batch_start.configure(state="disabled")
        self.prog_bar.set(0); self.lbl_prog.configure(text="Starting…")
        self._set_status("● Downloading…", C["accent"])
        threading.Thread(target=self._worker, args=(urls,), daemon=True).start()

    def _worker(self, urls):
        opts = self._build_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            for idx, url in enumerate(urls):
                if self.cancel_flag: break
                self.gui_q.put(("status_txt", f"Processing {idx+1}/{len(urls)}"))
                try:
                    info  = ydl.extract_info(url)
                    title = info.get("title","") if info else ""
                    if not self.cancel_flag: self._add_history(url, title)
                except Exception as e:
                    if not self.cancel_flag: self.gui_q.put(("log", f"✖ {e}"))
        self.gui_q.put(("cancelled",) if self.cancel_flag else ("done",))

    # ── batch queue ───────────────────────────────────────────────────────────
    def _batch_add_dialog(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Add URLs"); win.geometry("540x320")
        win.configure(fg_color=C["bg"]); win.grab_set()
        ctk.CTkLabel(win, text="Paste URLs (one per line):", font=FONT_BODY,
                      text_color=C["text"]).pack(anchor="w", padx=16, pady=(14,4))
        txt = ctk.CTkTextbox(win, fg_color=C["card"], border_color=C["border"],
                              border_width=1, font=FONT_MONO)
        txt.pack(fill="both", expand=True, padx=16)
        def _add():
            lines = [l.strip() for l in txt.get("0.0","end").split("\n") if l.strip()]
            for u in lines:
                row = BatchRow(self.batch_scroll, u, self._remove_batch_row)
                self.batch_rows.append(row)
            win.destroy()
        ctk.CTkButton(win, text="Add to Queue", height=38, fg_color=C["accent"],
                       hover_color=C["accent2"], command=_add).pack(fill="x", padx=16, pady=12)

    def _remove_batch_row(self, row):
        if row in self.batch_rows: self.batch_rows.remove(row)
        row.destroy()

    def _batch_clear(self):
        for r in list(self.batch_rows): self._remove_batch_row(r)

    def _start_batch(self):
        urls = [r.url for r in self.batch_rows]
        if not urls: return
        self._start_dl(urls)

    # ── poll queue ────────────────────────────────────────────────────────────
    def _poll(self):
        try:
            while True:
                task = self.gui_q.get_nowait()
                t = task[0]
                if t == "progress":
                    _, pct, info, fname = task
                    self.prog_bar.set(pct); self.lbl_prog.configure(text=info)
                    for row in self.batch_rows:
                        if fname and row.url in fname: row.update_progress(pct, info)
                    if not self.is_paused:
                        self.btn_start.configure(text="Pause", fg_color=C["amber"], state="normal")
                elif t == "status_txt":
                    self._set_status(f"● {task[1]}", C["accent"])
                elif t == "log":
                    self.log_box.insert("end", task[1]+"\n"); self.log_box.see("end")
                elif t == "meta":
                    self.lbl_meta_title.configure(text=task[1])
                    self.lbl_meta_sub.configure(text=task[2] if len(task)>2 else "")
                elif t == "done":
                    messagebox.showinfo("Done", "All downloads completed!")
                    self._reset_ui()
                elif t == "cancelled":
                    self._set_status("● Cancelled", C["muted"]); self._reset_ui()
                elif t == "history_refresh":
                    self._render_history()
                self.gui_q.task_done()
        except queue.Empty: pass
        self.root.after(80, self._poll)

    def _reset_ui(self):
        self.is_dl = False; self.is_paused = False; self.cancel_flag = False
        self.btn_start.configure(text="Start Download", fg_color=C["accent"], state="normal")
        self.btn_cancel.configure(state="disabled", text="Cancel")
        self.btn_batch_start.configure(state="normal")
        self.prog_bar.set(0); self.lbl_prog.configure(text="")
        self._set_status("● Ready", C["green"])

    # ── yt-dlp updater ────────────────────────────────────────────────────────
    def _update_ytdlp(self):
        self.log("Updating yt-dlp…")
        def _run():
            try:
                subprocess.check_call([sys.executable,"-m","pip","install","--upgrade","yt-dlp"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.gui_q.put(("log","✔ yt-dlp updated successfully."))
            except Exception as e:
                self.gui_q.put(("log",f"✖ Update failed: {e}"))
        threading.Thread(target=_run, daemon=True).start()

# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = ctk.CTk()
    App(root)
    root.mainloop()