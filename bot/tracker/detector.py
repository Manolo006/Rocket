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
        self.cooldown_seconds = config.get("detection_cooldown_seconds", 5)
        self.scan_interval = config.get("ocr_scan_interval_seconds", 0.5)
        self.multi_scan_duration = config.get("ocr_multi_scan_duration_seconds", 8)
        self.ocr_enabled = config.get("ocr_enabled", True) and HAS_RAPIDOCR
        
        # State machine
        self.state = "IDLE"  # IDLE, IN_MATCH, COOLDOWN
        self.last_detection_time = 0
        self.scoreboard_consumed = False
        
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

    def detect_mode_from_items(self, items):
        """
        Rileva la modalita (1v1, 2v2, 3v3) contando le righe giocatori distinte
        nella colonna centrale del tabellone (cx: 360-540, cy: 150-420).
        """
        player_ys = []
        for it in items:
            text = it['text'].strip()
            cx = it['cx']
            cy = it['cy']
            if 360 <= cx <= 540 and 150 <= cy <= 420:
                t_up = text.upper()
                if not any(k in t_up for k in ['PUNTEGGIO', 'GOL', 'ASSIST', 'PARATE', 'DANNO', 'PING', 'ARANCIONE', 'BLU', 'TEAM', 'TORNEO', 'BUTTON']):
                    if not any(abs(cy - py) < 18 for py in player_ys):
                        player_ys.append(cy)
        count = len(player_ys)
        if count >= 5:
            return "3v3"
        elif count in [3, 4]:
            return "2v2"
        elif count in [1, 2]:
            return "1v1"
        return None

    def extract_match_data_from_ocr(self, frame):
        """
        Esegue OCR sull'immagine di gioco ed estrae:
        1. Esito: Vittoria (True), Sconfitta (False) o None
        2. Delta Punti MMR esatto: es. +8, +9, +10, +11, -8, -10, -16 (o None)
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

            # 1. VERIFICA RIGIDA: E' davvero il tabellone post-match?
            # Supporta sia interfaccia in Inglese che in Italiano
            scoreboard_markers = [
                # Inglese
                'SCOREBOARD', 'SCOREBOARO', 'LEAVING IN', 'LEAVINGIN',
                'PLAY AGAIN', 'SAVE REPLAY', 'SAVEREPLAY', 'CHANGE PLAYLIST',
                # Italiano
                'CLASSIFICA', 'ABBANDONO TRA', 'ABBANDONOTRA', 'ABBANDONO',
                'GIOCA DI NUOVO', 'SALVA IL REPLAY', 'CAMBIA PLAYLIST',
                'VINCITORE', 'PREMI', 'SEGNALA/BLOCCA', 'NASCONDI CLASSIFICA',
                'SCALDAPANCHINA', 'NON CLASSIFICATO'
            ]
            has_scoreboard = any(m in full_text for m in scoreboard_markers)
            if not has_scoreboard:
                # Non siamo sul tabellone di fine partita: nessun trigger!
                return None, None, ""

            # 2. CERCA IL GIOCATORE TARGET (es. manolo20006 o [OH] manolo20006)
            player_clean = self.player_name.lower().replace('[oh]', '').strip()
            player_item = None
            if player_clean:
                candidates = []
                for it in items:
                    if player_clean in it['text'].lower():
                        candidates.append(it)

                if candidates:
                    # Preferisci il candidato nella tabella centrale (cx > 200, cy < 460)
                    # evitando il banner avatar nell'HUD in basso a sinistra (cy > 500, cx < 200)
                    table_candidates = [c for c in candidates if c['cy'] < 460 and c['cx'] > 200]
                    player_item = table_candidates[0] if table_candidates else candidates[0]

            # Se il nome del giocatore e' configurato ma non e' sul tabellone, non rischiare
            if player_clean and not player_item:
                return None, None, ""

            p_cy = player_item['cy'] if player_item else None

            # Rileva automaticamente la modalita dal tabellone (conteggio giocatori) se disponibile
            detected_mode = self.detect_mode_from_items(items)
            if detected_mode and detected_mode != self.current_mode:
                print(f"[Detector] Modalita rilevata da tabellone OCR: {detected_mode}")
                self.set_mode(detected_mode)

            # 3. CERCA I DELTA PUNTI SULLA RIGA DEL GIOCATORE
            delta_pattern = re.compile(r'(?:^|[\s\(\[\{])([+-]\s*\d{1,2})(?:[\s\.,\)\}\]]|$)', re.IGNORECASE)
            joined_pattern = re.compile(r'^([+-]\s*\d{1,2})(\d{3,4})')

            row_deltas = []
            all_deltas = []

            for it in items:
                t = it['text'].strip()
                cy = it['cy']

                val = None
                mj = joined_pattern.match(t)
                if mj:
                    v = int(mj.group(1).replace(' ', ''))
                    if abs(v) <= 50:
                        val = v
                else:
                    m = delta_pattern.search(t)
                    if m:
                        v = int(m.group(1).replace(' ', ''))
                        if abs(v) <= 50:
                            val = v

                if val is not None:
                    all_deltas.append({'val': val, 'cy': cy})
                    # Se vicino alla riga del player (entro 25 pixel verticali)
                    if p_cy is not None and abs(cy - p_cy) <= 25:
                        row_deltas.append(val)

            chosen_points = None
            if row_deltas:
                # Abbiamo trovato il delta esattamente sulla riga di manolo20006!
                chosen_points = row_deltas[0]
            elif p_cy is None and all_deltas:
                chosen_points = all_deltas[0]['val']

            # Se abbiamo trovato i punti specifici della riga
            if chosen_points is not None:
                is_win = (chosen_points > 0)
                return is_win, chosen_points, f"Rilevato su riga {self.player_name}: {chosen_points:+d}"

            # Se siamo sul tabellone ma BakkesMod non ha la colonna MMR:
            # Fallback intelligente tramite banner
            is_win = None
            if any(w in full_text for w in ['VITTORIA', 'WINNER', 'VICTORY', 'HAI VINTO', 'DIVISION UP']):
                is_win = True
            elif any(w in full_text for w in ['SCONFITTA', 'DEFEAT', 'HAI PERSO', 'DIVISION DOWN']):
                is_win = False

            if is_win is not None:
                points = self.default_win_points if is_win else self.default_loss_points
                return is_win, points, "Esito da banner tabellone"

            return None, None, ""

        except Exception as e:
            print(f"[Detector] Eccezione durante estrazione OCR: {e}")
            return None, None, ""

    def scan_post_match_screen(self, rl_window=None, duration=8):
        """
        Effettua una scansione OCR multi-passaggio rapida attendendo la comparsa
        del tabellone di fine partita con il nome del giocatore.
        """
        start_time = time.time()
        attempt = 0

        self.notify_status(f"Match concluso! Lettura tabellone per {self.player_name}...")
        print(f"[Detector] Inizio scansione OCR per {self.player_name}...")

        while (time.time() - start_time) < duration and self.running:
            attempt += 1
            frame = self.capture_game_screen(rl_window)
            if frame is not None:
                is_win, points, details = self.extract_match_data_from_ocr(frame)
                if is_win is not None and points is not None:
                    print(f"[Detector] OCR Tentativo {attempt}: SUCCESSO! Esito={is_win} Punti={points:+d} ({details})")
                    return is_win, points, details

            time.sleep(0.2)

        print("[Detector] Nessun tabellone valido con punteggio per il giocatore rilevato.")
        return None, None, ""

    def trigger_match_result(self, is_win, points=None):
        now = time.time()
        if now - self.last_detection_time < 3:
            print("[Detector] Ignorato trigger match: troppo vicino all'ultimo.")
            return False

        self.last_detection_time = now
        self.scoreboard_consumed = True
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
        # 1. Rilevamento automatico della modalita di gioco da log/playlist
        mode_found = None
        if any(k in line for k in ["RankedSoloDuel"]):
            mode_found = "1v1"
        elif any(k in line for k in ["RankedTeamDoubles", "RankedHoops"]):
            mode_found = "2v2"
        elif any(k in line for k in ["RankedStandard", "RankedBreakout", "RankedRumble", "RankedSnowDay"]):
            mode_found = "3v3"
        else:
            m_pl = re.search(r'Playlist(?:Id)?\s*[=:]\s*\(?(\d+)', line)
            if m_pl:
                pid = int(m_pl.group(1))
                if pid in [1, 10]:
                    mode_found = "1v1"
                elif pid in [2, 11, 27]:
                    mode_found = "2v2"
                elif pid in [3, 4, 13, 28, 29, 30]:
                    mode_found = "3v3"

        if mode_found and mode_found != self.current_mode:
            print(f"[Detector] Modalita aggiornata da log: {mode_found}")
            self.set_mode(mode_found)

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

                # 1. Gestione Cooldown anti-duplicazione non bloccante
                if self.state == "COOLDOWN":
                    elapsed = now - self.last_detection_time
                    if elapsed >= self.cooldown_seconds:
                        self.state = "IDLE"
                    else:
                        remaining = max(1, int(self.cooldown_seconds - elapsed))
                        self.notify_status(f"Partita registrata ({self.current_mode})! Pronto in {remaining}s...")

                # 2. Verifica se Rocket League e in esecuzione
                rl_window = self.find_rocket_league_window()

                # 3. Controllo continuo del file di Log Rocket League
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
                            # Se rileva l'inizio o la ricerca di un nuovo match, resetta subito il tabellone
                            if any(k in line for k in ["OpeningLoadingScreen", "StartJoin", "StartMatchmaking", "TryToPlayOnlineWithAntiCheat"]):
                                self.scoreboard_consumed = False
                                self.state = "IDLE"

                            if self._parse_log_line(line):
                                print(f"[Detector] Fine match rilevata da log: {line.strip()[:80]}")
                                match_ended_from_log = True
                                self.scoreboard_consumed = False
                                break

                # 4. Scansione post-match istantanea da trigger log
                if match_ended_from_log and not self.scoreboard_consumed and rl_window:
                    is_win, points, details = self.scan_post_match_screen(rl_window, duration=self.multi_scan_duration)
                    if is_win is not None and points is not None:
                        self.trigger_match_result(is_win=is_win, points=points)
                        continue
                    else:
                        print(f"[Detector] Fine match da log, ma tabellone/punti per {self.player_name} non confermati.")

                # 5. Vision check istantaneo (cattura subito la schermata se il tabellone e gia a video)
                if rl_window and self.ocr_enabled:
                    frame = self.capture_game_screen(rl_window)
                    if frame is not None:
                        is_win, points, details = self.extract_match_data_from_ocr(frame)
                        if is_win is not None and points is not None:
                            # Se c'e il tabellone e non e ancora stato consumato per questo match
                            if not self.scoreboard_consumed and (now - self.last_detection_time >= 3):
                                print(f"[Detector] Tabellone rilevato istantaneamente a video per {self.player_name}: {details}")
                                self.trigger_match_result(is_win=is_win, points=points)
                                continue
                        else:
                            # Se il tabellone NON e a schermo e sono passati almeno 3 secondi,
                            # significa che il giocatore e uscito verso menu/coda/nuovo match:
                            # ripristina immediatamente lo stato IDLE e scoreboard_consumed = False!
                            if self.scoreboard_consumed and (now - self.last_detection_time >= 3):
                                print("[Detector] Uscito dal tabellone: bot pronto istantaneamente per la prossima partita.")
                                self.scoreboard_consumed = False
                                self.state = "IDLE"

                if rl_window:
                    if self.state != "COOLDOWN":
                        self.notify_status(f"Rocket League attivo ({self.current_mode}) - Monitoraggio OCR istantaneo...")
                    time.sleep(self.scan_interval)
                else:
                    self.notify_status("In attesa di Rocket League...")
                    time.sleep(1.5)

            except Exception as e:
                print(f"[Detector] Errore loop detector: {e}")
                time.sleep(1)

        if log_fp:
            try:
                log_fp.close()
            except Exception:
                pass

