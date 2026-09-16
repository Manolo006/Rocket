import json
import time
from datetime import datetime
from pathlib import Path

class SessionManager:
    def __init__(self, config_path=None, sync_service=None):
        self.sync_service = sync_service
        self.data_file = Path(__file__).resolve().parent.parent / "session_data.json"
        
        self.active = False
        self.session_id = None
        self.start_time = None
        self.last_match_time = None
        
        self.matches = []
        self.wins = 0
        self.losses = 0
        self.balance_points = 0
        self.current_win_streak = 0
        self.current_lose_streak = 0
        self.best_win_streak = 0
        self.best_lose_streak = 0

        self.load_state()

    def load_state(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.active = data.get("active", False)
                    self.session_id = data.get("session_id")
                    self.start_time = data.get("start_time")
                    self.last_match_time = data.get("last_match_time")
                    self.matches = data.get("matches", [])
                    self.recalculate_stats()
            except Exception as e:
                print(f"[SessionManager] Errore caricamento sessione: {e}")

    def save_state(self):
        try:
            data = {
                "active": self.active,
                "session_id": self.session_id,
                "start_time": self.start_time,
                "last_match_time": self.last_match_time,
                "matches": self.matches,
                "summary": self.get_summary()
            }
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[SessionManager] Errore salvataggio sessione: {e}")

    def start_new_session(self):
        now = time.time()
        self.active = True
        self.session_id = f"session_{int(now)}"
        self.start_time = now
        self.last_match_time = now
        self.matches = []
        self.wins = 0
        self.losses = 0
        self.balance_points = 0
        self.current_win_streak = 0
        self.current_lose_streak = 0
        self.best_win_streak = 0
        self.best_lose_streak = 0
        
        self.save_state()
        if self.sync_service:
            self.sync_service.broadcast_event("session_started", self.get_summary())
        print(f"[SessionManager] Nuova sessione avviata ({datetime.fromtimestamp(now).strftime('%H:%M:%S')})")

    def end_session(self):
        self.active = False
        self.save_state()
        if self.sync_service:
            self.sync_service.broadcast_event("session_ended", self.get_summary())
        print("[SessionManager] Sessione terminata.")

    def check_auto_session_timeout(self, timeout_minutes=45):
        if not self.active or not self.last_match_time:
            return False
        elapsed = time.time() - self.last_match_time
        if elapsed > (timeout_minutes * 60):
            print(f"[SessionManager] Inattivita rilevata ({int(elapsed/60)} min). Reset sessione.")
            self.start_new_session()
            return True
        return False

    def add_match(self, mode, points):
        now = time.time()
        if not self.active:
            self.start_new_session()

        match_info = {
            "mode": mode,
            "points": points,
            "timestamp": now,
            "result": "WIN" if points > 0 else "LOSS"
        }
        self.matches.append(match_info)
        self.last_match_time = now
        self.recalculate_stats()
        self.save_state()

        if self.sync_service:
            self.sync_service.broadcast_event("session_updated", self.get_summary())

    def recalculate_stats(self):
        self.wins = 0
        self.losses = 0
        self.balance_points = 0
        self.current_win_streak = 0
        self.current_lose_streak = 0
        self.best_win_streak = 0
        self.best_lose_streak = 0

        for m in self.matches:
            pts = m.get("points", 0)
            self.balance_points += pts
            if pts > 0:
                self.wins += 1
                self.current_win_streak += 1
                self.current_lose_streak = 0
                if self.current_win_streak > self.best_win_streak:
                    self.best_win_streak = self.current_win_streak
            elif pts < 0:
                self.losses += 1
                self.current_lose_streak += 1
                self.current_win_streak = 0
                if self.current_lose_streak > self.best_lose_streak:
                    self.best_lose_streak = self.current_lose_streak
            else:
                self.current_win_streak = 0
                self.current_lose_streak = 0

    def get_summary(self):
        total = len(self.matches)
        win_rate = (self.wins / total * 100.0) if total > 0 else 0.0
        last_m = self.matches[-1] if self.matches else None

        by_mode = {
            "1v1": {"games": 0, "wins": 0, "losses": 0, "balance": 0},
            "2v2": {"games": 0, "wins": 0, "losses": 0, "balance": 0},
            "3v3": {"games": 0, "wins": 0, "losses": 0, "balance": 0}
        }
        for m in self.matches:
            m_mode = m.get("mode", "2v2")
            if m_mode not in by_mode:
                by_mode[m_mode] = {"games": 0, "wins": 0, "losses": 0, "balance": 0}
            by_mode[m_mode]["games"] += 1
            pts = m.get("points", 0)
            by_mode[m_mode]["balance"] += pts
            if pts > 0:
                by_mode[m_mode]["wins"] += 1
            elif pts < 0:
                by_mode[m_mode]["losses"] += 1

        return {
            "active": self.active,
            "session_id": self.session_id,
            "total_games": total,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(win_rate, 1),
            "balance": self.balance_points,
            "current_win_streak": self.current_win_streak,
            "current_lose_streak": self.current_lose_streak,
            "best_win_streak": self.best_win_streak,
            "best_lose_streak": self.best_lose_streak,
            "last_match": last_m,
            "by_mode": by_mode,
            "start_time": self.start_time,
            "last_match_time": self.last_match_time
        }
