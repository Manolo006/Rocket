import os
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

class TrackerHUD:
    def __init__(self, detector, session_manager, sync_service, config):
        self.detector = detector
        self.session_manager = session_manager
        self.sync_service = sync_service
        self.config = config

        self.root = tk.Tk()
        self.root.title("Rocket Tracker • Companion")
        self.root.geometry("380x520")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0e1322")

        # Set up styles
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Variables
        self.mode_var = tk.StringVar(value=self.config.get("default_mode", "2v2"))
        self.status_var = tk.StringVar(value="Inizializzazione...")
        self.points_custom_var = tk.StringVar(value="9")
        self.always_on_top_var = tk.BooleanVar(value=True)

        self._build_ui()

        # Connect detector callback
        self.detector.set_status_callback(self.update_status_threadsafe)

        # Global key bindings
        self.root.bind("<F9>", lambda e: self.on_quick_win())
        self.root.bind("<F10>", lambda e: self.on_quick_loss())
        self.root.bind("<F8>", lambda e: self.on_new_session())

        # Start periodic GUI refresh for session stats
        self.refresh_session_ui()

    def _build_ui(self):
        # Header Frame
        header = tk.Frame(self.root, bg="#161d36", padx=16, pady=12)
        header.pack(fill="x")

        title_label = tk.Label(header, text="ROCKET TRACKER", font=("Inter", 13, "bold"), fg="#7da7ff", bg="#161d36")
        title_label.pack(side="left")

        top_cb = tk.Checkbutton(
            header, text="Sempre in primo piano", variable=self.always_on_top_var,
            command=self.toggle_topmost, bg="#161d36", fg="#a0aec0",
            selectcolor="#0e1322", activebackground="#161d36", font=("Inter", 8)
        )
        top_cb.pack(side="right")

        # Status Bar
        self.status_frame = tk.Frame(self.root, bg="#1a223f", padx=12, pady=8)
        self.status_frame.pack(fill="x", padx=14, pady=(12, 6))

        self.status_label = tk.Label(
            self.status_frame, textvariable=self.status_var, font=("Inter", 9, "bold"),
            fg="#6ee7b7", bg="#1a223f", wraplength=340, justify="center"
        )
        self.status_label.pack()

        # Mode Selection
        mode_frame = tk.LabelFrame(self.root, text=" Modalità di Gioco ", font=("Inter", 9, "bold"),
                                   fg="#d2d9ff", bg="#0e1322", padx=10, pady=8)
        mode_frame.pack(fill="x", padx=14, pady=6)

        btn_box = tk.Frame(mode_frame, bg="#0e1322")
        btn_box.pack(fill="x")

        for m in ["1v1", "2v2", "3v3"]:
            rb = tk.Radiobutton(
                btn_box, text=m, value=m, variable=self.mode_var, command=self.on_mode_change,
                font=("Inter", 10, "bold"), fg="#ffffff", bg="#0e1322", selectcolor="#2563eb",
                indicatoron=0, padx=18, pady=5, activebackground="#3b82f6"
            )
            rb.pack(side="left", expand=True, fill="x", padx=3)

        # Quick Actions Frame
        action_frame = tk.LabelFrame(self.root, text=" Registrazione Rapida ", font=("Inter", 9, "bold"),
                                     fg="#d2d9ff", bg="#0e1322", padx=10, pady=8)
        action_frame.pack(fill="x", padx=14, pady=6)

        act_box = tk.Frame(action_frame, bg="#0e1322")
        act_box.pack(fill="x")

        win_btn = tk.Button(
            act_box, text="🏆 VITTORIA (+9)\n[F9]", font=("Inter", 10, "bold"),
            bg="#059669", fg="#ffffff", activebackground="#10b981", activeforeground="#ffffff",
            relief="flat", padx=10, pady=8, cursor="hand2", command=self.on_quick_win
        )
        win_btn.pack(side="left", expand=True, fill="x", padx=3)

        loss_btn = tk.Button(
            act_box, text="❌ SCONFITTA (-9)\n[F10]", font=("Inter", 10, "bold"),
            bg="#dc2626", fg="#ffffff", activebackground="#ef4444", activeforeground="#ffffff",
            relief="flat", padx=10, pady=8, cursor="hand2", command=self.on_quick_loss
        )
        loss_btn.pack(side="right", expand=True, fill="x", padx=3)

        # Custom points bar
        custom_box = tk.Frame(action_frame, bg="#0e1322", pady=6)
        custom_box.pack(fill="x")

        tk.Label(custom_box, text="Punti custom:", font=("Inter", 8), fg="#94a3b8", bg="#0e1322").pack(side="left")
        
        for p in [8, 10]:
            btn = tk.Button(
                custom_box, text=f"+{p}", font=("Inter", 8, "bold"), bg="#1e293b", fg="#38bdf8",
                relief="flat", padx=8, pady=2, cursor="hand2",
                command=lambda val=p: self.on_custom_match(val)
            )
            btn.pack(side="left", padx=2)

        for p in [-8, -10]:
            btn = tk.Button(
                custom_box, text=f"{p}", font=("Inter", 8, "bold"), bg="#1e293b", fg="#f87171",
                relief="flat", padx=8, pady=2, cursor="hand2",
                command=lambda val=p: self.on_custom_match(val)
            )
            btn.pack(side="left", padx=2)

        # Session Stats Frame
        stats_frame = tk.LabelFrame(self.root, text=" Sessione Corrente [F8 Nuova] ", font=("Inter", 9, "bold"),
                                    fg="#d2d9ff", bg="#0e1322", padx=10, pady=8)
        stats_frame.pack(fill="x", padx=14, pady=6)

        self.stats_grid = tk.Frame(stats_frame, bg="#0e1322")
        self.stats_grid.pack(fill="x")

        self.lbl_games = self._make_stat_box(self.stats_grid, 0, 0, "Partite", "0")
        self.lbl_wl = self._make_stat_box(self.stats_grid, 0, 1, "V / S", "0 - 0")
        self.lbl_winrate = self._make_stat_box(self.stats_grid, 0, 2, "Win %", "0%")
        self.lbl_balance = self._make_stat_box(self.stats_grid, 1, 0, "Bilancio", "0")
        self.lbl_streak = self._make_stat_box(self.stats_grid, 1, 1, "Streak", "0")
        self.lbl_best = self._make_stat_box(self.stats_grid, 1, 2, "Top Win", "0")

        # Session Control Buttons
        sess_btn_box = tk.Frame(stats_frame, bg="#0e1322", pady=4)
        sess_btn_box.pack(fill="x")

        new_sess_btn = tk.Button(
            sess_btn_box, text="🔄 Nuova Sessione", font=("Inter", 8, "bold"),
            bg="#2563eb", fg="#ffffff", activebackground="#3b82f6", relief="flat",
            padx=8, pady=4, cursor="hand2", command=self.on_new_session
        )
        new_sess_btn.pack(side="left", expand=True, fill="x", padx=2)

        dash_btn = tk.Button(
            sess_btn_box, text="🌐 Apri Dashboard", font=("Inter", 8, "bold"),
            bg="#1e293b", fg="#93c5fd", activebackground="#334155", relief="flat",
            padx=8, pady=4, cursor="hand2", command=self.open_dashboard
        )
        dash_btn.pack(side="right", expand=True, fill="x", padx=2)

    def _make_stat_box(self, parent, row, col, label_text, default_val):
        frame = tk.Frame(parent, bg="#131b31", padx=6, pady=4, relief="groove", borderwidth=1)
        frame.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
        parent.grid_columnconfigure(col, weight=1)

        val_lbl = tk.Label(frame, text=default_val, font=("Inter", 11, "bold"), fg="#ffffff", bg="#131b31")
        val_lbl.pack()

        sub_lbl = tk.Label(frame, text=label_text, font=("Inter", 7), fg="#94a3b8", bg="#131b31")
        sub_lbl.pack()

        return val_lbl

    def toggle_topmost(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())

    def on_mode_change(self):
        new_mode = self.mode_var.get()
        self.detector.set_mode(new_mode)

    def on_quick_win(self):
        mode = self.mode_var.get()
        pts = self.config.get("win_points", 9)
        self.detector.trigger_match_result(is_win=True, points=pts)

    def on_quick_loss(self):
        mode = self.mode_var.get()
        pts = self.config.get("loss_points", -9)
        self.detector.trigger_match_result(is_win=False, points=pts)

    def on_custom_match(self, points):
        mode = self.mode_var.get()
        is_win = points > 0
        self.detector.trigger_match_result(is_win=is_win, points=points)

    def on_new_session(self):
        self.session_manager.start_new_session()
        self.update_status_threadsafe("Nuova sessione avviata!")

    def open_dashboard(self):
        mode = self.mode_var.get()
        url = f"https://manolo006.github.io/Rocket/{mode}.html"
        webbrowser.open(url)

    def update_status_threadsafe(self, text):
        def _update():
            self.status_var.set(text)
        self.root.after(0, _update)

    def refresh_session_ui(self):
        try:
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
        except Exception:
            pass

        # Check auto timeout
        timeout = self.config.get("auto_session_timeout_minutes", 45)
        self.session_manager.check_auto_session_timeout(timeout)

        # Refresh every 1000ms
        self.root.after(1000, self.refresh_session_ui)

    def start(self):
        self.root.mainloop()
