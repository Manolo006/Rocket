import sys
import time
import requests
from pathlib import Path

bot_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(bot_dir))

from tracker.session_manager import SessionManager
from tracker.sync_service import SyncService
from tracker.detector import MatchDetector

def test_all():
    print('--- 1. Testing SessionManager ---')
    sm = SessionManager()
    sm.start_new_session()
    assert sm.active is True
    sm.add_match('2v2', 9)
    sm.add_match('2v2', 9)
    sm.add_match('2v2', -9)
    summary = sm.get_summary()
    print('Session summary:', summary)
    assert summary['total_games'] == 3
    assert summary['wins'] == 2
    assert summary['losses'] == 1
    assert summary['balance'] == 9
    assert summary['best_win_streak'] == 2
    print('SessionManager OK!')

    print("--- 2. Testing SyncService Local Companion Server ---")
    config = {
        'firebase_database_url': 'https://rocketleaguestatss-default-rtdb.europe-west1.firebasedatabase.app',
        'scope': 'guests/local',
        'default_mode': '2v2',
        'local_server_port': 59123
    }
    sync = SyncService(config, session_manager=sm)
    sync.start_local_server()
    time.sleep(0.5)

    res = requests.get('http://127.0.0.1:59123/api/status', timeout=2)
    assert res.status_code == 200
    data = res.json()
    print('API status response:', data)
    assert data['status'] == 'running'
    print('SyncService Local Server OK!')

    print("--- 3. Testing Detector initialization ---")
    detector = MatchDetector(config)
    print('Detector OK, status:', detector.state)

    sync.stop()
    print(">>> ALL TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == '__main__':
    test_all()
