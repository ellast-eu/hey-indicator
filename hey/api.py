"""API HTTP locale (bibliothèque standard uniquement) et mini-page de commande.

GET  /               page de commande (téléphone, PC)
GET  /api/status     état complet en JSON
POST /api/mode       {"mode": "free" | "busy"}
POST /api/on_air     {"on": true | false}   (sans "on" : bascule)
POST /api/hey        {"text": "message facultatif"}
POST /api/urgency
POST /api/ack        acquitte hey / urgency
POST /api/timer      {"action": "start" | "pause" | "toggle" | "reset", "minutes": 25}
POST /api/brightness {"value": 1..100}

Si un jeton est configuré (HEY_TOKEN), chaque POST doit porter l'en-tête
« Authorization: Bearer <jeton> ». Le trafic est en clair : à réserver au
réseau local.
"""

import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 4096

PAGE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>hey-indicator</title>
<style>
  body { font-family: system-ui, sans-serif; background: #111; color: #eee;
         max-width: 26rem; margin: 0 auto; padding: 16px; }
  h1 { font-size: 1.1rem; letter-spacing: .08em; }
  #state { font: 700 2rem ui-monospace, monospace; padding: 18px; text-align: center;
           border-radius: 10px; background: #000; margin-bottom: 16px; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
  button, input { font: inherit; padding: 14px; border-radius: 10px; border: 1px solid #444;
           background: #222; color: #eee; }
  input { width: 100%; box-sizing: border-box; margin-bottom: 10px; }
  button:active { background: #333; }
  .free { color: #2ee06a; } .busy, .on_air, .urgency, .focus { color: #ff4a3a; }
  .hey { color: #ffc800; } .break { color: #3c96ff; }
</style></head><body>
<h1>HEY-INDICATOR</h1>
<div id="state">...</div>
<div class="row"><button onclick="post('mode',{mode:'free'})">Free</button>
<button onclick="post('mode',{mode:'busy'})">Busy</button></div>
<div class="row"><button onclick="post('on_air',{})">On Air</button>
<button onclick="post('ack',{})">Acquitter</button></div>
<input id="msg" maxlength="60" placeholder="Message (facultatif)">
<div class="row"><button onclick="post('hey',{text:msg.value})">Hey!</button>
<button onclick="post('urgency',{})">Urgent</button></div>
<div class="row"><button onclick="post('timer',{action:'toggle'})">Focus start / pause</button>
<button onclick="post('timer',{action:'reset'})">Reset</button></div>
<script>
const state = document.getElementById('state'), msg = document.getElementById('msg');
let token = sessionStorage.getItem('hey_token') || '';
async function post(path, body) {
  const headers = {'Content-Type': 'application/json'};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const r = await fetch('/api/' + path, {method: 'POST', headers, body: JSON.stringify(body)});
  if (r.status === 401) {
    token = prompt('Jeton :') || '';
    sessionStorage.setItem('hey_token', token);
    if (token) return post(path, body);
  }
  refresh();
}
async function refresh() {
  try {
    const s = await (await fetch('/api/status')).json();
    let label = s.screen.replace('_', ' ').toUpperCase();
    if (s.timer.phase !== 'idle') {
      const left = Math.ceil(s.timer.remaining);
      label += ' ' + String(Math.floor(left / 60)).padStart(2, '0') + ':' + String(left % 60).padStart(2, '0');
    }
    state.textContent = label; state.className = s.screen;
  } catch (e) { state.textContent = 'hors ligne'; state.className = ''; }
}
refresh(); setInterval(refresh, 1000);
</script></body></html>
"""


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def make_handler(indicator, cfg, display=None):
    def route_post(path, body):
        if path == "/api/mode":
            try:
                indicator.set_mode(body.get("mode"))
            except ValueError as error:
                raise ApiError(400, str(error))
        elif path == "/api/on_air":
            on = body.get("on")
            if on is not None and not isinstance(on, bool):
                raise ApiError(400, "on attendu : true ou false")
            indicator.set_on_air(on)
        elif path == "/api/hey":
            indicator.hey(body.get("text", ""))
        elif path == "/api/urgency":
            indicator.urgency()
        elif path == "/api/ack":
            indicator.acknowledge()
        elif path == "/api/timer":
            action = body.get("action", "toggle")
            minutes = body.get("minutes")
            if minutes is not None and (isinstance(minutes, bool)
                                        or not isinstance(minutes, (int, float))):
                raise ApiError(400, "minutes attendu : un nombre")
            if action == "start":
                indicator.timer_start(minutes)
            elif action == "pause":
                indicator.timer_pause()
            elif action == "toggle":
                indicator.timer_toggle()
            elif action == "reset":
                indicator.timer_reset()
            else:
                raise ApiError(400, "action attendue : start, pause, toggle ou reset")
        elif path == "/api/brightness":
            value = body.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ApiError(400, "value attendu : 1 à 100")
            if display is not None:
                display.set_brightness(value)
        else:
            raise ApiError(404, "route inconnue")

    class Handler(BaseHTTPRequestHandler):
        server_version = "hey-indicator"

        def log_message(self, *args):       # pas de journal sur le terminal
            pass

        def _send(self, status, payload, content_type="application/json"):
            data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif path == "/api/status":
                self._send(200, indicator.snapshot())
            else:
                self._send(404, {"error": "route inconnue"})

        def do_POST(self):
            try:
                if cfg.token:
                    given = self.headers.get("Authorization", "")
                    expected = "Bearer " + cfg.token
                    if not hmac.compare_digest(given.encode(), expected.encode()):
                        raise ApiError(401, "jeton manquant ou invalide")
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    raise ApiError(400, "Content-Length invalide")
                if length < 0 or length > MAX_BODY:
                    raise ApiError(413, "corps trop volumineux")
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw) if raw.strip() else {}
                except ValueError:
                    raise ApiError(400, "JSON invalide")
                if not isinstance(body, dict):
                    raise ApiError(400, "objet JSON attendu")
                route_post(self.path.split("?", 1)[0], body)
                self._send(200, indicator.snapshot())
            except ApiError as error:
                self._send(error.status, {"error": str(error)})

    return Handler


def start_server(indicator, cfg, display=None):
    """Lance le serveur dans un fil d'exécution et le renvoie."""
    server = ThreadingHTTPServer((cfg.http_host, cfg.http_port),
                                 make_handler(indicator, cfg, display))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
