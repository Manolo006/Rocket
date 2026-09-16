import os
import sys
import time
from datetime import datetime
import webbrowser
import tkinter as tk
from tkinter import ttk
from pathlib import Path

class TrackerHUD:
    def __init__(self, detector, session_manager, sync_service, config):
        self.detector = detector
        self.session_manager = session_manager
        self.sync_service = sync_service
        self.config = config

        self.root = tk.Tk()
        self.root.title("Rocket Tracker • Auto Session Monitor")
        self.root.geometry("380x470")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0e1322")

        # Set up styles
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Variables
        self.mode_var = tk.StringVar(value=self.detector.current_mode)
        self.status_var = tk.StringVar(value="🟢 Inizializzazione OCR...")
        self.always_on_top_var = tk.BooleanVar(value=True)
        self.last_match_var = tk.StringVar(value="In attesa della prima partita...")

        self.mode_buttons = {}
        self._build_ui()

        # Connect detector callback
        self.detector.set_status_callback(self.update_status_threadsafe)

        # Global key binding for New Session only
        self.root.bind("<F8>", lambda e: self.on_new_session())

        # Start periodic GUI refresh for session stats and mode sync
        self.refresh_session_ui()

    def _build_ui(self):
        # 1. Header Frame
        header = tk.Frame(self.root, bg="#161d36", padx=16, pady=10)
        header.pack(fill="x")

        title_label = tk.Label(header, text="ROCKET TRACKER • AUTO", font=("Inter", 12, "bold"), fg="#7da7ff", bg="#161d36")
        title_label.pack(side="left")

        top_cb = tk.Checkbutton(
            header, text="In primo piano", variable=self.always_on_top_var,
            command=self.toggle_topmost, bg="#161d36", fg="#a0aec0",
            selectcolor="#0e1322", activebackground="#161d36", font=("Inter", 8)
        )
        top_cb.pack(side="right")

        # 2. Live Status Bar
        self.status_frame = tk.Frame(self.root, bg="#1a223f", padx=12, pady=8)
        self.status_frame.pack(fill="x", padx=14, pady=(10, 6))

        self.status_label = tk.Label(
            self.status_frame, textvariable=self.status_var, font=("Inter", 9, "bold"),
            fg="#6ee7b7", bg="#1a223f", wraplength=340, justify="center"
        )
        self.status_label.pack()

        # 3. Auto-Detected Lobby Mode Frame
        mode_frame = tk.LabelFrame(self.root, text=" Modalità Sessione (Rilevata Automaticamente) ",
                                   font=("Inter", 9, "bold"), fg="#d2d9ff", bg="#0e1322", padx=10, pady=8)
        mode_frame.pack(fill="x", padx=14, pady=6)

        btn_box = tk.Frame(mode_frame, bg="#0e1322")
        btn_box.pack(fill="x")

        for m in ["1v1", "2v2", "3v3"]:
            btn = tk.Button(
                btn_box, text=m, font=("Inter", 10, "bold"),
                fg="#64748b", bg="#131b31", activebackground="#2563eb", activeforeground="#ffffff",
                relief="flat", padx=12, pady=5, cursor="hand2",
                command=lambda val=m: self.on_manual_mode_click(val)
            )
            btn.pack(side="left", expand=True, fill="x", padx=3)
            self.mode_buttons[m] = btn

        self.lbl_mode_detected = tk.Label(
            mode_frame, text=f"Lobby Rilevata: {self.mode_var.get()} (Auto)",
            font=("Inter", 8, "italic"), fg="#93c5fd", bg="#0e1322", pady=4
        )
        self.lbl_mode_detected.pack()

        # 4. Session Scores Frame
        stats_frame = tk.LabelFrame(self.root, text=" Score della Sessione Corrente ",
                                    font=("Inter", 9, "bold"), fg="#d2d9ff", bg="#0e1322", padx=10, pady=8)
        stats_frame.pack(fill="x", padx=14, pady=6)

        self.stats_grid = tk.Frame(stats_frame, bg="#0e1322")
        self.stats_grid.pack(fill="x")

        self.lbl_games = self._make_stat_box(self.stats_grid, 0, 0, "Partite", "0")
        self.lbl_wl = self._make_stat_box(self.stats_grid, 0, 1, "V / S", "0 - 0")
        self.lbl_winrate = self._make_stat_box(self.stats_grid, 0, 2, "Win %", "0%")
        self.lbl_balance = self._make_stat_box(self.stats_grid, 1, 0, "Bilancio MMR", "0")
        self.lbl_streak = self._make_stat_box(self.stats_grid, 1, 1, "Streak", "0")
        self.lbl_best = self._make_stat_box(self.stats_grid, 1, 2, "Top Win", "0")

        # 5. Last Match Box
        last_match_frame = tk.Frame(stats_frame, bg="#131b31", padx=8, pady=5, relief="groove", borderwidth=1)
        last_match_frame.pack(fill="x", pady=(8, 2))

        self.lbl_last_match = tk.Label(
            last_match_frame, textvariable=self.last_match_var,
            font=("Inter", 8, "bold"), fg="#38bdf8", bg="#131b31", wraplength=320, justify="center"
        )
        self.lbl_last_match.pack()

        # 6. Session Controls (New Session + Open Dashboard)
        sess_btn_box = tk.Frame(self.root, bg="#0e1322", padx=14, pady=8)
        sess_btn_box.pack(fill="x")

        new_sess_btn = tk.Button(
            sess_btn_box, text="🔄 Nuova Sessione [F8]", font=("Inter", 9, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#3b82f6", relief="flat",
            padx=10, pady=6, cursor="hand2", command=self.on_new_session
        )
        new_sess_btn.pack(side="left", expand=True, fill="x", padx=3)

        dash_btn = tk.Button(
            sess_btn_box, text="🌐 Apri Dashboard Web", font=("Inter", 9, "bold"),
            bg="#1e293b", fg="#93c5fd", activebackground="#334155", relief="flat",
            padx=10, pady=6, cursor="hand2", command=self.open_dashboard
        )
        dash_btn.pack(side="right", expand=True, fill="x", padx=3)

    def _make_stat_box(self, parent, row, col, label_text, default_val):
        frame = tk.Frame(parent, bg="#131b31", padx=6, pady=5, relief="groove", borderwidth=1)
        frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
        parent.grid_columnconfigure(col, weight=1)

        val_lbl = tk.Label(frame, text=default_val, font=("Inter", 11, "bold"), fg="#ffffff", bg="#131b31")
        val_lbl.pack()

        sub_lbl = tk.Label(frame, text=label_text, font=("Inter", 7), fg="#94a3b8", bg="#131b31")
        sub_lbl.pack()

        return val_lbl

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def on_manual_mode_click(self, mode):
        self.mode_var.set(mode)
        self.detector.set_mode(mode)
        self._update_mode_badges(mode)

    def on_new_session(self):
        self.session_manager.start_new_session()
        self.last_match_var.set("Nuova sessione avviata! In attesa di partite...")
        self.update_status_threadsafe("Nuova sessione avviata!")

    def open_dashboard(self):
        mode = self.detector.current_mode or self.mode_var.get()
        url = f"https://manolo006.github.io/Rocket/{mode}.html"
        webbrowser.open(url)

    def update_status_threadsafe(self, text):
        def _update():
            self.status_var.set(text)
        self.root.after(0, _update)

    def _update_mode_badges(self, active_mode):
        for m, btn in self.mode_buttons.items():
            if m == active_mode:
                btn.config(bg="#2563eb", fg="#ffffff")
            else:
                btn.config(bg="#131b31", fg="#64748b")
        if hasattr(self, 'lbl_mode_detected'):
            self.lbl_mode_detected.config(text=f"Lobby Rilevata: {active_mode} (Automatico • Punti a {active_mode})")

    def refresh_session_ui(self):
        try:
            # 1. Sync detected mode from detector
            active_mode = self.detector.current_mode
            if active_mode and active_mode != self.mode_var.get():
                self.mode_var.set(active_mode)
            self._update_mode_badges(self.mode_var.get())

            # 2. Update session scores
            summary = self.session_manager.get_summary()
            total = summary.get("total_games", 0)
            wins = summary.get("wins", 0)
            losses = summary.get("losses", 0)
            win_rate = summary.get("win_rate", 0)
            balance = summary.get("balance", 0)
            streak = summary.get("current_win_streak", 0)
            if streak == 0 and summary.get("current_lose_streak", 0) > 0:
                streak = -summary.get("current_lose_streak", 0)
            best_win = summary.get("best_win_streak", 0)

            self.lbl_games.config(text=str(total))
            self.lbl_wl.config(text=f"{wins}W - {losses}L")
            self.lbl_winrate.config(text=f"{win_rate}%")
            
            bal_str = f"{balance:+d}" if balance != 0 else "0"
            self.lbl_balance.config(text=bal_str, fg="#4ade80" if balance > 0 else ("#f87171" if balance < 0 else "#ffffff"))

            streak_str = f"{streak:+d}" if streak != 0 else "0"
            self.lbl_streak.config(text=streak_str)
            self.lbl_best.config(text=str(best_win))

            # 3. Update last match text
            last_m = summary.get("last_match")
            if last_m:
                m_mode = last_m.get("mode", "2v2")
                m_pts = last_m.get("points", 0)
                m_res = "Vittoria" if m_pts > 0 else "Sconfitta"
                m_time = datetime.fromtimestamp(last_m.get("timestamp", time.time())).strftime("%H:%M")
                icon = "🏆" if m_pts > 0 else "❌"
                self.last_match_var.set(f"{icon} Ultimo match: {m_mode} • {m_res} ({m_pts:+d} MMR) [{m_time}]")
        except Exception:
            pass

        # Check auto timeout
        timeout = self.config.get("auto_session_timeout_minutes", 45)
        self.session_manager.check_auto_session_timeout(timeout)

        # Refresh every 600ms
        self.root.after(600, self.refresh_session_ui)

    def start(self):
        self.root.mainloop()
