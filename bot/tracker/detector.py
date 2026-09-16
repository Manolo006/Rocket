import os
import re
import time
import threading
from pathlib import Path
import numpy as np
import pygetwindow as gw
import cv2

try:
    from PIL import ImageGrab
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    from rapidocr_onnxruntime import RapidOCR
    HAS_RAPIDOCR = True
except ImportError:
    HAS_RAPIDOCR = False

class MatchDetector:
    def __init__(self, config, on_match_detected=None):
        self.config = config
        self.on_match_detected = on_match_detected
        self.running = False
        self.thread = None
        
        # Paths
        raw_log = config.get("log_file_path", "~/Documents/My Games/Rocket League/TAGame/Logs/Launch.log")
        self.log_path = Path(os.path.expanduser(raw_log))
        
        # Player & Mode Settings
        self.player_name = config.get("player_name", "manolo20006")
        self.current_mode = config.get("default_mode", "2v2")
        self.default_win_points = config.get("win_points", 9)
        self.default_loss_points = config.get("loss_points", -9)
        self.cooldown_seconds = config.get("detection_cooldown_seconds", 35)
        self.multi_scan_duration = config.get("ocr_multi_scan_duration_seconds", 8)
        self.ocr_enabled = config.get("ocr_enabled", True) and HAS_RAPIDOCR
        
        # State machine
        self.state = "IDLE"  # IDLE, IN_MATCH, COOLDOWN
        self.last_detection_time = 0
        
        # Callback for GUI status updates
        self.on_status_change = None

        # OCR Engine (inizializzato una sola volta)
        self.ocr = None
        if self.ocr_enabled:
            try:
                print("[Detector] Inizializzazione RapidOCR...")
                self.ocr = RapidOCR()
                print("[Detector] RapidOCR pronto per la lettura a schermo.")
            except Exception as e:
                print(f"[Detector] Errore inizializzazione RapidOCR: {e}")
                self.ocr_enabled = False

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

    def capture_game_screen(self, window=None):
        """
        Cattura l'immagine della finestra di gioco (o dello schermo primario)
        con fallback tra PIL ImageGrab e MSS.
        Ritorna un'immagine BGR numpy ndarray o None.
        """
        bbox = None
        if window:
            try:
                left = max(0, int(window.left))
                top = max(0, int(window.top))
                right = left + int(window.width)
                bottom = top + int(window.height)
                if right > left and bottom > top:
                    bbox = (left, top, right, bottom)
            except Exception:
                bbox = None

        # 1. Tentativo con PIL ImageGrab
        if HAS_PIL:
            try:
                if bbox:
                    img = ImageGrab.grab(bbox=bbox)
                else:
                    img = ImageGrab.grab()
                return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            except Exception:
                pass

        # 2. Fallback con MSS
        if HAS_MSS:
            try:
                with mss.MSS() as sct:
                    if bbox:
                        mon = {"left": bbox[0], "top": bbox[1], "width": bbox[2] - bbox[0], "height": bbox[3] - bbox[1]}
                    else:
                        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                        if mon["left"] < 0: mon["left"] = 0
                        if mon["top"] < 0: mon["top"] = 0
                    grabbed = sct.grab(mon)
                    arr = np.array(grabbed)
                    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR) if arr.shape[2] == 4 else arr
            except Exception:
                pass

        return None

    def extract_match_data_from_ocr(self, frame):
        """
        Esegue OCR sull'immagine di gioco ed estrae:
        1. Esito: Vittoria (True), Sconfitta (False) o None
        2. Delta Punti MMR esatto: es. +8, +9, +10, +11, -8, -10 (o None)
        3. Stringa testuale completa rilevata
        """
        if self.ocr is None or frame is None:
            return None, None, ""

        try:
            ocr_results, _ = self.ocr(frame)
            if not ocr_results:
                return None, None, ""

            raw_texts = []
            items = []
            for item in ocr_results:
                text = str(item[1]).strip()
                conf = float(item[2]) if len(item) > 2 else 1.0
                box = item[0]
                cy = (box[0][1] + box[2][1]) / 2.0
                cx = (box[0][0] + box[2][0]) / 2.0
                raw_texts.append(text)
                items.append({'text': text, 'conf': conf, 'cx': cx, 'cy': cy, 'box': box})

            full_text = ' '.join(raw_texts).upper()

            # 1. Determina l'esito (Vittoria o Sconfitta)
            is_win = None
            win_keywords = ['VITTORIA', 'WINNER', 'VICTORY', 'HAI VINTO', 'WIN', 'PROMOSSO', 'DIVISION UP', 'SALITO']
            loss_keywords = ['SCONFITTA', 'DEFEAT', 'HAI PERSO', 'LOSS', 'RETROCESSO', 'DIVISION DOWN', 'SCESO']

            for kw in win_keywords:
                if kw in full_text:
                    is_win = True
                    break

            if is_win is None:
                for kw in loss_keywords:
                    if kw in full_text:
                        is_win = False
                        break

            # 2. Riconoscimento schermata post-match / tabellone
            is_post_match = any(w in full_text for w in [
                'SCOREBOARD', 'SCOREBOARO', 'LEAVING IN', 'LEAVINGIN',
                'PLAY AGAIN', 'SAVE REPLAY', 'SAVEREPLAY', 'DIVISION UP',
                'DIVISION DOWN', 'VITTORIA', 'SCONFITTA', 'WINNER', 'DEFEAT'
            ])

            # 3. Cerca delta punti MMR (es. +9, -8, (+10), (-7), +9 MMR, +9 661, +9669)
            candidates = []
            delta_pattern = re.compile(r'(?:^|[\s\(\[\{])([+-]\s*\d+(?:[\.,]\d+)?)(?:[\)\]\}\s]|MMR|PTS|PUNTI|$)', re.IGNORECASE)
            paren_pattern = re.compile(r'\(\s*([+-]?\d+(?:[\.,]\d+)?)\s*\)')
            # Supporto per delta incollato a MMR totale (es. +9669 -> delta: +9, totale: 669)
            joined_pattern = re.compile(r'^([+-]\s*\d{1,2})(\d{3,4})')

            for it in items:
                t = it['text'].strip()

                # A. Pattern delta incollato a MMR totale (BakkesMod)
                m_j = joined_pattern.match(t)
                if m_j:
                    val = float(m_j.group(1).replace(' ', ''))
                    if abs(val) <= 50:
                        candidates.append({'val': val, 'item': it, 'has_sign': True})
                        continue

                # B. Pattern delta standard con segno esplicito
                m = delta_pattern.search(t)
                if m:
                    clean = m.group(1).replace(' ', '').replace(',', '.')
                    try:
                        val = float(clean)
                        # Un delta reale di Rocket League e' tipicamente tra -50 e +50
                        if abs(val) <= 50:
                            candidates.append({'val': val, 'item': it, 'has_sign': True})
                    except ValueError:
                        pass

                # C. Pattern numero tra parentesi
                m_paren = paren_pattern.search(t)
                if m_paren:
                    clean = m_paren.group(1).replace(' ', '').replace(',', '.')
                    try:
                        val = float(clean)
                        if abs(val) <= 50:
                            candidates.append({'val': val, 'item': it, 'has_sign': ('+' in clean or '-' in clean)})
                    except ValueError:
                        pass

            chosen_points = None

            # Se abbiamo il nome del player, cerchiamo il candidato piu vicino sulla stessa riga (tabellone)
            if self.player_name and candidates:
                p_lower = self.player_name.lower()
                player_item = None
                for it in items:
                    if p_lower in it['text'].lower():
                        player_item = it
                        break
                if player_item:
                    candidates.sort(key=lambda c: abs(c['item']['cy'] - player_item['cy']))
                    chosen_points = int(round(candidates[0]['val']))

            # Se non trovato tramite nome, filtriamo in base all'esito
            if chosen_points is None and candidates:
                if is_win is True:
                    positives = [c for c in candidates if c['val'] > 0]
                    if positives:
                        chosen_points = int(round(positives[0]['val']))
                elif is_win is False:
                    negatives = [c for c in candidates if c['val'] < 0]
                    if negatives:
                        chosen_points = int(round(negatives[0]['val']))

                if chosen_points is None:
                    signed = [c for c in candidates if c['has_sign']]
                    if signed:
                        chosen_points = int(round(signed[0]['val']))
                    else:
                        chosen_points = int(round(candidates[0]['val']))

            if is_win is None and chosen_points is not None:
                is_win = (chosen_points >= 0)

            # Normalizzazione coerenza tra segno ed esito
            if chosen_points is not None and is_win is not None:
                if is_win and chosen_points < 0:
                    chosen_points = abs(chosen_points)
                elif not is_win and chosen_points > 0:
                    chosen_points = -abs(chosen_points)

            return is_win, chosen_points, full_text

        except Exception as e:
            print(f"[Detector] Eccezione durante estrazione OCR: {e}")
            return None, None, ""

    def scan_post_match_screen(self, rl_window=None, duration=8):
        """
        Effettua una scansione OCR multi-passaggio per alcuni secondi
        in modo da intercettare sia il banner iniziale (Vittoria/Sconfitta)
        sia il tabellone successivo con i delta MMR (+10, -8, ecc.).
        """
        start_time = time.time()
        best_win = None
        best_points = None
        best_details = ""
        attempt = 0

        self.notify_status("Fine match! Lettura automatica con OCR in corso...")
        print("[Detector] Inizio scansione OCR multi-passaggio post-match...")

        while (time.time() - start_time) < duration and self.running:
            attempt += 1
            frame = self.capture_game_screen(rl_window)
            if frame is not None:
                is_win, points, details = self.extract_match_data_from_ocr(frame)
                if is_win is not None and best_win is None:
                    best_win = is_win
                if points is not None:
                    best_points = points
                    best_details = details
                    print(f"[Detector] OCR Tentativo {attempt}: Rilevato esito={is_win} punti={points:+d}")
                    break
                elif is_win is not None:
                    print(f"[Detector] OCR Tentativo {attempt}: Rilevato esito={is_win}, in attesa dei numeri MMR...")

            time.sleep(1.2)

        if best_win is not None and best_points is None:
            best_points = self.default_win_points if best_win else self.default_loss_points
            print(f"[Detector] Nessun delta MMR a video: uso punti di default ({best_points:+d})")

        return best_win, best_points, best_details

    def trigger_match_result(self, is_win, points=None):
        now = time.time()
        if now - self.last_detection_time < 10:
            print("[Detector] Ignorato trigger match: troppo vicino all'ultimo.")
            return False

        self.last_detection_time = now
        self.state = "COOLDOWN"

        if points is None:
            points = self.default_win_points if is_win else self.default_loss_points

        result_label = "VITTORIA" if is_win else "SCONFITTA"
        self.notify_status(f"{result_label} rilevata! ({points:+d} MMR) -> Salvataggio automatico...")
        print(f"\n[Detector] >>> EVENTO REGISTRATO: {result_label} | Modalita: {self.current_mode} | Punti: {points:+d} <<<")

        if self.on_match_detected:
            try:
                self.on_match_detected(self.current_mode, points, result_label)
            except Exception as e:
                print(f"[Detector] Errore esecuzione callback match: {e}")

        return True

    def _parse_log_line(self, line):
        """
        Analizza le righe del Launch.log per aggiornare la modalita e rilevare fine partita.
        """
        # 1. Rilevamento automatico della modalita di gioco
        if "RankedReconnect:" in line or "UpdateRankedReconnect()" in line:
            if "RankedTeamDoubles" in line:
                if self.current_mode != "2v2":
                    print("[Detector] Modalita aggiornata da log: 2v2")
                    self.set_mode("2v2")
            elif "RankedSoloDuel" in line:
                if self.current_mode != "1v1":
                    print("[Detector] Modalita aggiornata da log: 1v1")
                    self.set_mode("1v1")
            elif "RankedStandard" in line:
                if self.current_mode != "3v3":
                    print("[Detector] Modalita aggiornata da log: 3v3")
                    self.set_mode("3v3")

        # 2. Rilevamento automatico del nickname del player locale
        if "ViewerPRI=PRI_TA_0" in line and "UpdatePlayerName" in line:
            m = re.search(r'ViewerPRI=PRI_TA_0\s+([^\s\(\)]+)', line)
            if m:
                detected_name = m.group(1).strip()
                if detected_name and detected_name != self.player_name:
                    print(f"[Detector] Player name rilevato da log: {detected_name}")
                    self.player_name = detected_name

        # 3. Rilevamento evento di conclusione partita
        match_end_triggers = [
            "Party: Ranked Game Finished",
            "ClearRankedReconnect()",
            "HandleRewardDropNotification",
            "Prime_MatchComplete",
            "GFX_WinnerMenu_SF.upk"
        ]
        for trigger in match_end_triggers:
            if trigger in line:
                return True

        return False

    def _detection_loop(self):
        log_fp = None
        current_log_path = None

        while self.running:
            try:
                now = time.time()

                # Gestione Cooldown anti-duplicazione
                if self.state == "COOLDOWN":
                    remaining = int(self.cooldown_seconds - (now - self.last_detection_time))
                    if remaining > 0:
                        self.notify_status(f"In attesa del prossimo match (cooldown {remaining}s)...")
                        time.sleep(2)
                        continue
                    else:
                        self.state = "IDLE"

                # 1. Verifica se Rocket League e in esecuzione
                rl_window = self.find_rocket_league_window()

                # 2. Controllo Log Watcher se il file esiste
                match_ended_from_log = False
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
                            if self._parse_log_line(line):
                                print(f"[Detector] Fine match rilevata da log: {line.strip()[:80]}")
                                match_ended_from_log = True
                                break

                # Se intercettata fine match da log, avvia scansione OCR multi-passaggio
                if match_ended_from_log and self.state != "COOLDOWN":
                    is_win, points, _ = self.scan_post_match_screen(rl_window, duration=self.multi_scan_duration)
                    if is_win is not None:
                        self.trigger_match_result(is_win=is_win, points=points)
                        continue
                    else:
                        self.trigger_match_result(is_win=True)
                        continue

                # 3. Vision check periodico con OCR se finestra attiva (backup)
                if self.state == "IDLE" and self.ocr_enabled and rl_window:
                    frame = self.capture_game_screen(rl_window)
                    if frame is not None:
                        is_win, points, _ = self.extract_match_data_from_ocr(frame)
                        if is_win is not None:
                            print(f"[Detector] OCR Vision attiva: rilevato esito={is_win} punti={points}")
                            self.trigger_match_result(is_win=is_win, points=points)
                            time.sleep(3)
                            continue

                if rl_window:
                    self.notify_status(f"Rocket League attivo ({self.current_mode}) - Monitoraggio OCR automatico...")
                else:
                    self.notify_status("In attesa di Rocket League...")

                time.sleep(1.5)

            except Exception as e:
                print(f"[Detector] Errore loop detector: {e}")
                time.sleep(2)

        if log_fp:
            try:
                log_fp.close()
            except Exception:
                pass

