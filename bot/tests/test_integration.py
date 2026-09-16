import sys
import time
import requests
from pathlib import Path

bot_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(bot_dir))

from tracker.session_manager import SessionManager
from tracker.sync_service import SyncService

def test_integration():
    print('=== INTEGRATION TEST: Rocket Tracker Bot ===')
    
    # 1. Config
    config = {
        'firebase_database_url': 'https://rocketleaguestatss-default-rtdb.europe-west1.firebasedatabase.app',
        'scope': 'guests/local',
        'default_mode': '2v2',
        'local_server_port': 59128
    }
    
    # 2. Setup Services
    sm = SessionManager()
    sm.start_new_session()
    sync = SyncService(config, session_manager=sm)
    sm.sync_service = sync
    sync.start_local_server()
    time.sleep(0.5)
    
    # 3. Test Status Endpoint
    res = requests.get('http://127.0.0.1:59128/api/status', timeout=3)
    assert res.status_code == 200, f'Status code {res.status_code}'
    status = res.json()
    print('1. Server Status OK:', status['status'])
    
    # 4. Record a Match
    print('2. Recording match: 2v2 (+9 points)...')
    record_result = sync.record_match('2v2', 9)
    assert record_result['success'] is True
    print('   Match recorded! Game data:', record_result['game'])
    if record_result.get('firebase_id'):
        print('   Firebase ID:', record_result['firebase_id'])
    
    # 5. Check Session updated
    summary = sm.get_summary()
    print('3. Session updated:', summary)
    assert summary['total_games'] >= 1
    assert summary['wins'] >= 1
    
    # 6. Test trigger endpoint
    print('4. Testing HTTP POST /api/game trigger...')
    post_res = requests.post('http://127.0.0.1:59128/api/game', json={'mode': '2v2', 'points': -9}, timeout=3)
    assert post_res.status_code == 200
    print('   POST /api/game OK!')
    
    # Clean up test matches
    if record_result.get('firebase_id'):
        fid = record_result['firebase_id']
        requests.delete(f"{config['firebase_database_url']}/{sync.scope}/games/2v2/{fid}.json")
    try:
        data_post = post_res.json()
        if data_post.get('result', {}).get('firebase_id'):
            fid2 = data_post['result']['firebase_id']
            requests.delete(f"{config['firebase_database_url']}/{sync.scope}/games/2v2/{fid2}.json")
    except Exception:
        pass
    
    sync.stop()
    print('\n>>> ALL INTEGRATION TESTS PASSED 100%! <<<')

if __name__ == '__main__':
    test_integration()
