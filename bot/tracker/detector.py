import os
import time
import threading
from pathlib import Path
import numpy as np
from PIL import ImageGrab
import pygetwindow as gw
import cv2

class MatchDetector:
    def __init__(self, config, on_match_detected=None):
        self.config = config
        self.on_match_detected = on_match_detected
        self.running = False
        self.thread = None
        
        # Paths
        raw_log = config.get("log_file_path", "~/Documents/My Games/Rocket League/TAGame/Logs/Launch.log")
        self.log_path = Path(os.path.expanduser(raw_log))
        
        # State machine
        self.state = "IDLE"  # IDLE, IN_MATCH, COOLDOWN
        self.last_detection_time = 0
        self.cooldown_seconds = config.get("detection_cooldown_seconds", 35)
        self.default_win_points = config.get("win_points", 9)
        self.default_loss_points = config.get("loss_points", -9)
        self.current_mode = config.get("default_mode", "2v2")
        
        # Callback for GUI status updates
        self.on_status_change = None

    def set_status_callback(self, cb):
        self.on_status_change = cb

    def set_mode(self, mode):
        self.current_mode = mode
        self.notify_status(f"Modalita impostata: {mode}")

    def notify_status(self, text):
        if self.on_status_change:
            try:
                self.on_status_change(text)
            except Exception:
                pass

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        print("[Detector] Rilevatore avviato in background.")

    def stop(self):
        self.running = False

    def find_rocket_league_window(self):
        for title in gw.getAllTitles():
            if "Rocket League" in title:
                windows = gw.getWindowsWithTitle(title)
                if windows and windows[0].width > 300 and windows[0].height > 200:
                    return windows[0]
        return None

    def analyze_screen_banner(self, window):
        """
        Analizza la porzione centrale superiore dello schermo dove compare
        il banner di vittoria/sconfitta in Rocket League.
        """
        try:
            left = window.left + int(window.width * 0.20)
            top = window.top + int(window.height * 0.15)
            right = window.left + int(window.width * 0.80)
            bottom = window.top + int(window.height * 0.50)

            if right <= left or bottom <= top:
                return None

            img = ImageGrab.grab(bbox=(left, top, right, bottom))
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            # Maschera Blu (Squadra Blu / Vittoria Blu)
            blue_lower = np.array([95, 120, 120])
            blue_upper = np.array([130, 255, 255])
            blue_mask = cv2.inRange(hsv, blue_lower, blue_upper)
            blue_ratio = np.count_nonzero(blue_mask) / (frame.shape[0] * frame.shape[1])

            # Maschera Arancione (Squadra Arancione / Vittoria Arancione)
            orange_lower = np.array([8, 140, 140])
            orange_upper = np.array([25, 255, 255])
            orange_mask = cv2.inRange(hsv, orange_lower, orange_upper)
            orange_ratio = np.count_nonzero(orange_mask) / (frame.shape[0] * frame.shape[1])

            # Maschera Giallo/Oro (Scritta WINNER / VITTORIA / Stelle)
            gold_lower = np.array([20, 150, 180])
            gold_upper = np.array([35, 255, 255])
            gold_mask = cv2.inRange(hsv, gold_lower, gold_upper)
            gold_ratio = np.count_nonzero(gold_mask) / (frame.shape[0] * frame.shape[1])

            if gold_ratio > 0.02 or blue_ratio > 0.08 or orange_ratio > 0.08:
                return {
                    "detected": True,
                    "blue_ratio": blue_ratio,
                    "orange_ratio": orange_ratio,
                    "gold_ratio": gold_ratio
                }
            return None
        except Exception:
            return None

    def trigger_match_result(self, is_win, points=None):
        now = time.time()
        if now - self.last_detection_time < 5:
            print("[Detector] Ignorato trigger match: troppo vicino all'ultimo.")
            return False

        self.last_detection_time = now
        self.state = "COOLDOWN"
        
        if points is None:
            points = self.default_win_points if is_win else self.default_loss_points

        result_label = "VITTORIA" if is_win else "SCONFITTA"
        self.notify_status(f"{result_label} rilevata! ({points:+d} punti) -> Registrazione...")
        print(f"[Detector] Evento match: {result_label} | Modalita: {self.current_mode} | Punti: {points:+d}")

        if self.on_match_detected:
            try:
                self.on_match_detected(self.current_mode, points, result_label)
            except Exception as e:
                print(f"[Detector] Errore esecuzione callback: {e}")

        return True

    def _detection_loop(self):
        log_fp = None
        current_log_path = None

        while self.running:
            try:
                now = time.time()

                # Gestione Cooldown
                if self.state == "COOLDOWN":
                    remaining = int(self.cooldown_seconds - (now - self.last_detection_time))
                    if remaining > 0:
                        self.notify_status(f"In attesa del prossimo match (cooldown {remaining}s)...")
                        time.sleep(2)
                        continue
                    else:
                        self.state = "IDLE"

                # 1. Verifica se Rocket League è in esecuzione
                rl_window = self.find_rocket_league_window()
                if not rl_window:
                    self.notify_status("In attesa di Rocket League...")
                    time.sleep(3)
                    continue

                # 2. Controllo Log Watcher se il file esiste
                if self.log_path.exists():
                    if log_fp is None or current_log_path != self.log_path:
                        try:
                            if log_fp:
                                log_fp.close()
                            log_fp = open(self.log_path, "r", encoding="utf-8", errors="ignore")
                            log_fp.seek(0, os.SEEK_END)
                            current_log_path = self.log_path
                        except Exception:
                            log_fp = None

                    if log_fp:
                        while True:
                            line = log_fp.readline()
                            if not line:
                                break
                            if "Prime_MatchComplete" in line or "MatchComplete" in line:
                                print(f"[Detector] Evento log intercettato: {line.strip()[:80]}")
                                banner = self.analyze_screen_banner(rl_window)
                                is_win = True
                                if banner and banner.get("orange_ratio", 0) > 0.15:
                                    is_win = True
                                self.trigger_match_result(is_win=is_win)
                                break

                # 3. Vision check periodico se Rocket League è la finestra attiva
                if self.state == "IDLE":
                    banner = self.analyze_screen_banner(rl_window)
                    if banner and banner["detected"]:
                        print(f"[Detector] Banner visivo rilevato: {banner}")
                        self.trigger_match_result(is_win=True)
                        time.sleep(3)
                        continue

                self.notify_status(f"Rocket League attivo ({self.current_mode}) - In ascolto...")
                time.sleep(1.5)

            except Exception as e:
                print(f"[Detector] Errore loop detector: {e}")
                time.sleep(2)

        if log_fp:
            try:
                log_fp.close()
            except Exception:
                pass
