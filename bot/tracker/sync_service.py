import json
import time
import queue
import threading
import requests
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

class SyncService:
    def __init__(self, config, session_manager=None):
        self.config = config
        self.session_manager = session_manager
        self.firebase_url = config.get("firebase_database_url", "").rstrip("/")
        self.scope = config.get("scope", "guests/local")
        self.port = config.get("local_server_port", 59123)
        self.sse_clients = []
        self.lock = threading.Lock()
        self.server = None
        self.server_thread = None
        self.last_saved_game = None

    def start_local_server(self):
        sync_self = self
        
        class CompanionHTTPHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def send_cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

            def do_OPTIONS(self):
                self.send_response(204)
                self.send_cors_headers()
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                
                if parsed.path == "/api/status":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_cors_headers()
                    self.end_headers()
                    
                    status = {
                        "status": "running",
                        "active_mode": sync_self.config.get("default_mode", "2v2"),
                        "last_game": sync_self.last_saved_game,
                        "session": sync_self.session_manager.get_summary() if sync_self.session_manager else None
                    }
                    self.wfile.write(json.dumps(status).encode("utf-8"))
                    
                elif parsed.path == "/api/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.send_cors_headers()
                    self.end_headers()
                    
                    q = queue.Queue()
                    with sync_self.lock:
                        sync_self.sse_clients.append(q)
                    
                    init_data = json.dumps({"type": "connected", "time": time.time()})
                    self.wfile.write(f"data: {init_data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    
                    try:
                        while True:
                            try:
                                msg = q.get(timeout=20)
                                self.wfile.write(f"data: {msg}\n\n".encode("utf-8"))
                                self.wfile.flush()
                            except queue.Empty:
                                self.wfile.write(b": keepalive\n\n")
                                self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError):
                        pass
                    finally:
                        with sync_self.lock:
                            if q in sync_self.sse_clients:
                                sync_self.sse_clients.remove(q)
                else:
                    self.send_response(404)
                    self.send_cors_headers()
                    self.end_headers()

            def do_POST(self):
                parsed = urlparse(self.path)
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
                
                try:
                    data = json.loads(body) if body else {}
                except json.JSONDecodeError:
                    data = {}

                if parsed.path == "/api/game":
                    mode = data.get("mode", sync_self.config.get("default_mode", "2v2"))
                    points = int(data.get("points", 9))
                    res = sync_self.record_match(mode, points)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps(res).encode("utf-8"))
                    
                elif parsed.path == "/api/session":
                    action = data.get("action", "new")
                    if sync_self.session_manager:
                        if action == "new":
                            sync_self.session_manager.start_new_session()
                        elif action == "end":
                            sync_self.session_manager.end_session()
                            
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_cors_headers()
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "action": action}).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.send_cors_headers()
                    self.end_headers()

        try:
            self.server = HTTPServer(("127.0.0.1", self.port), CompanionHTTPHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            print(f"[SyncService] Local companion server running on http://127.0.0.1:{self.port}")
        except Exception as e:
            print(f"[SyncService] Warning: could not start local server on port {self.port}: {e}")

    def broadcast_event(self, event_type, payload):
        data = json.dumps({"type": event_type, "payload": payload, "time": time.time()})
        with self.lock:
            for q in list(self.sse_clients):
                try:
                    q.put_nowait(data)
                except Exception:
                    pass

    def record_match(self, mode, points, date_str=None, time_str=None):
        now = datetime.now()
        if not date_str:
            date_str = now.strftime("%Y-%m-%d")
        if not time_str:
            time_str = now.strftime("%H:%M")

        game_data = {
            "date": date_str,
            "time": time_str,
            "points": int(points),
            "createdAt": int(time.time() * 1000)
        }

        # 1. Update local session manager
        if self.session_manager:
            self.session_manager.add_match(mode, points)

        # 2. Push to Firebase Realtime Database
        firebase_id = None
        if self.firebase_url:
            url = f"{self.firebase_url}/{self.scope}/modes/{mode}/games.json"
            try:
                resp = requests.post(url, json=game_data, timeout=5)
                if resp.status_code == 200:
                    res_json = resp.json()
                    firebase_id = res_json.get("name")
                    print(f"[SyncService] Saved to Firebase! Mode: {mode}, Points: {points:+d}, ID: {firebase_id}")
                else:
                    print(f"[SyncService] Firebase HTTP error: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"[SyncService] Firebase connection failed: {e}")

        game_data["id"] = firebase_id
        game_data["mode"] = mode
        self.last_saved_game = game_data

        # 3. Broadcast to any open dashboard tabs via SSE
        self.broadcast_event("game_added", game_data)

        return {
            "success": True,
            "game": game_data,
            "firebase_id": firebase_id
        }

    def stop(self):
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
