import sys
import os
import time
import numpy as np
import cv2
from pathlib import Path

bot_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(bot_dir))

from tracker.detector import MatchDetector

def test_ocr_and_detector():
    print('====================================================')
    print('   TEST: OCR DETECTION & MMR POINTS EXTRACTION     ')
    print('====================================================')

    config = {
        'player_name': 'manolo20006',
        'default_mode': '2v2',
        'win_points': 9,
        'loss_points': -9,
        'detection_cooldown_seconds': 5,
        'ocr_enabled': True
    }

    detected_events = []
    def on_match(mode, pts, label):
        print(f'   [CALLBACK RECEIVED] Mode: {mode} | Points: {pts:+d} | Label: {label}')
        detected_events.append((mode, pts, label))

    detector = MatchDetector(config, on_match_detected=on_match)
    assert detector.ocr is not None, 'RapidOCR should be loaded'
    print('[PASS] MatchDetector & RapidOCR successfully initialized.')

    # 1. Test Synthesized Image: Victory with explicit MMR delta (+11)
    img_win = np.zeros((300, 800, 3), dtype=np.uint8)
    img_win[:] = (20, 25, 35) # Dark background
    cv2.putText(img_win, 'VITTORIA', (250, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 215, 255), 3)
    cv2.putText(img_win, 'manolo20006  (+11) MMR', (180, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
    cv2.putText(img_win, 'Opponent   (-11) MMR', (180, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (180, 180, 180), 2)

    is_win, pts, text = detector.extract_match_data_from_ocr(img_win)
    print(f'Test Win Screen -> is_win: {is_win}, points: {pts}, text: {text[:60]}...')
    assert is_win is True, f'Expected True, got {is_win}'
    assert pts == 11, f'Expected +11, got {pts}'
    print('[PASS] Victory +11 MMR correctly detected and associated with player!')

    # 2. Test Synthesized Image: Defeat with explicit MMR delta (-8)
    img_loss = np.zeros((300, 800, 3), dtype=np.uint8)
    img_loss[:] = (25, 20, 20)
    cv2.putText(img_loss, 'SCONFITTA', (230, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (50, 50, 230), 3)
    cv2.putText(img_loss, 'manolo20006  (-8) MMR', (180, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)

    is_win_loss, pts_loss, _ = detector.extract_match_data_from_ocr(img_loss)
    print(f'Test Loss Screen -> is_win: {is_win_loss}, points: {pts_loss}')
    assert is_win_loss is False, f'Expected False, got {is_win_loss}'
    assert pts_loss == -8, f'Expected -8, got {pts_loss}'
    print('[PASS] Defeat -8 MMR correctly detected!')

    # 3. Test Fallback: Banner only (No BakkesMod numbers on screen)
    img_banner_only = np.zeros((200, 600, 3), dtype=np.uint8)
    img_banner_only[:] = (30, 30, 30)
    cv2.putText(img_banner_only, 'VITTORIA', (150, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 215, 255), 3)

    is_win_b, pts_b, _ = detector.extract_match_data_from_ocr(img_banner_only)
    print(f'Test Banner Only -> is_win: {is_win_b}, points: {pts_b}')
    assert is_win_b is True
    # Without numbers, extract_match_data_from_ocr returns None for points (caller applies fallback)
    assert pts_b is None

    # Test trigger_match_result applying fallback
    detector.last_detection_time = 0 # reset debounce
    detector.trigger_match_result(is_win=True, points=None)
    assert len(detected_events) == 1
    assert detected_events[0] == ('2v2', 9, 'VITTORIA')
    print('[PASS] Fallback to default win_points (+9) applied seamlessly!')

    # 4. Test Log Line Parsing
    # Playlist detection
    assert detector._parse_log_line('RankedReconnect: UpdateRankedReconnect() RankedTeamDoubles True') is False
    assert detector.current_mode == '2v2'
    detector._parse_log_line('RankedReconnect: UpdateRankedReconnect() RankedSoloDuel True')
    assert detector.current_mode == '1v1'
    print('[PASS] Dynamic mode switching (1v1) from log verified!')

    detector._parse_log_line('RankedReconnect: UpdateRankedReconnect() RankedStandard True')
    assert detector.current_mode == '3v3'
    print('[PASS] Dynamic mode switching (3v3) from log verified!')

    # Match end detection
    assert detector._parse_log_line('[0906.02] Party: Ranked Game Finished, Clear party member server') is True
    assert detector._parse_log_line('[0906.02] RankedReconnect: RankedReconnectSave_TA_0.ClearRankedReconnect()') is True
    print('[PASS] Log match-finished triggers verified!')

    print('====================================================')
    print('   >>> ALL OCR & DETECTION TESTS PASSED (100%) <<<   ')
    print('====================================================')

if __name__ == '__main__':
    test_ocr_and_detector()
