import os
import sys
import json
import signal
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

from tracker.session_manager import SessionManager
from tracker.sync_service import SyncService
from tracker.detector import MatchDetector
from tracker.gui import TrackerHUD

def load_config():
    cfg_file = current_dir / "config.json"
    default_config = {
        "firebase_database_url": "https://rocketleaguestatss-default-rtdb.europe-west1.firebasedatabase.app",
        "scope": "guests/local",
        "default_mode": "2v2",
        "win_points": 9,
        "loss_points": -9,
        "auto_session_timeout_minutes": 45,
        "local_server_port": 59123,
        "detection_cooldown_seconds": 35,
        "sound_notifications": True
    }
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                default_config.update(loaded)
        except Exception as e:
            print(f"[Main] Errore lettura config.json: {e}")
    return default_config

def main():
    print("==================================================")
    print("      🚀 ROCKET LEAGUE AUTO-TRACKER BOT           ")
    print("==================================================")

    config = load_config()

    # 1. Initialize Session Manager
    session_manager = SessionManager(sync_service=None)

    # 2. Initialize Sync Service (Firebase + Companion Server)
    sync_service = SyncService(config, session_manager=session_manager)
    session_manager.sync_service = sync_service
    sync_service.start_local_server()

    # 3. Match detected callback
    def on_match_detected(mode, points, result_label):
        print(f"\n[MAIN] >>> REGISTRAZIONE PARTITA: {mode} | {result_label} ({points:+d}) <<<")
        sync_service.record_match(mode, points)

    # 4. Initialize Detector
    detector = MatchDetector(config, on_match_detected=on_match_detected)
    detector.start()

    # 5. Handle clean shutdown
    def shutdown(sig=None, frame=None):
        print("\n[Main] Arresto bot in corso...")
        detector.stop()
        sync_service.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)

    # 6. Launch GUI
    print("[Main] Avvio interfaccia HUD...")
    hud = TrackerHUD(detector, session_manager, sync_service, config)
    try:
        hud.start()
    finally:
        shutdown()

if __name__ == "__main__":
    main()
