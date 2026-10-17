"""Local web server: serves the editor UI and a JSON API.

Security model
  * username/password login (PBKDF2), HttpOnly SameSite=Strict session cookie
  * the tray icon opens a one-time-style link carrying a secret token; it only
    works from the same machine (loopback) and logs you in without a password
  * binding to anything other than 127.0.0.1 (e.g. 0.0.0.0) requires a password
  * POST requests must come from the page's own origin (CSRF protection)
"""
import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import api, paths, render

SESSION_TTL = 30 * 86400
LOOPBACK = ("127.0.0.1", "::1", "localhost")


# ------------------------------------------------------------------ auth store
class Auth:
    def __init__(self):
        self.sessions = {}
        self.fails = {}
        self.lock = threading.Lock()
        self.data = {}
        try:
            with open(paths.AUTH, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            pass

    @property
    def configured(self):
        return bool(self.data.get("user") and self.data.get("hash"))

    @staticmethod
    def _hash(pw, salt):
        return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()

    def set_password(self, user, pw):
        salt = secrets.token_bytes(16)
        self.data = {"user": user, "salt": salt.hex(), "hash": self._hash(pw, salt)}
        with open(paths.AUTH, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        with self.lock:
            self.sessions.clear()     # log everybody out

    def check(self, ip, user, pw):
        now = time.time()
        with self.lock:
            n, until = self.fails.get(ip, (0, 0))
            if until > now:
                return False, "Too many attempts – wait %ds" % (until - now)
        ok = self.configured and hmac.compare_digest(user, self.data["user"]) and hmac.compare_digest(
            self._hash(pw, bytes.fromhex(self.data["salt"])), self.data["hash"])
        with self.lock:
            if ok:
                self.fails.pop(ip, None)
            else:
                n += 1
                self.fails[ip] = (n, now + min(300, 2 ** n) if n >= 4 else 0)
        return ok, "" if ok else "Wrong username or password"

    def new_session(self):
        s = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[s] = time.time() + SESSION_TTL
        return s

    def valid(self, s):
        with self.lock:
            e = self.sessions.get(s or "")
            if e and e > time.time():
                return True
            self.sessions.pop(s or "", None)
            return False


def get_token():
    try:
        with open(paths.TOKEN) as f:
            t = f.read().strip()
            if t:
                return t
    except Exception:
        pass
    t = secrets.token_urlsafe(18)
    with open(paths.TOKEN, "w") as f:
        f.write(t)
    return t


def make_server(engine, port):
    token = get_token()
    auth = Auth()
    web = os.path.join(paths.resource_dir(), "web")
    bind = engine.cfg.get("bind", "127.0.0.1")
    warn = ""
    if bind not in LOOPBACK and not auth.configured:
        warn = "Network access needs a password: set one from the tray link, then restart."
        bind = "127.0.0.1"
    exposed = bind not in LOOPBACK

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        # ---- helpers
        def _ip(self):
            return self.client_address[0]

        def _local(self):
            return self._ip() in ("127.0.0.1", "::1")

        def _cookie(self):
            for part in (self.headers.get("Cookie") or "").split(";"):
                k, _, v = part.strip().partition("=")
                if k == "dc_session":
                    return v
            return ""

        def _authed(self):
            return auth.valid(self._cookie())

        def _host_ok(self):
            if exposed:
                return True
            return (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]") in LOOPBACK

        def _origin_ok(self):
            o = self.headers.get("Origin")
            if not o:
                return True
            return urlparse(o).netloc == self.headers.get("Host")

        def _send(self, code, body, ctype="application/json", headers=None):
            if isinstance(body, (dict, list)):
                body = json.dumps(body).encode()
            elif isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _session_cookie(self):
            return {"Set-Cookie": "dc_session=%s; Path=/; HttpOnly; SameSite=Strict; Max-Age=%d" % (
                auth.new_session(), SESSION_TTL)}

        # ---- GET
        def do_GET(self):
            u = urlparse(self.path)
            if not self._host_ok():
                return self._send(403, "bad host", "text/plain")
            q = parse_qs(u.query)
            if u.path in ("/", "/index.html"):
                t = q.get("t", [""])[0]
                if t and self._local() and hmac.compare_digest(t, token):
                    h = self._session_cookie()
                    h["Location"] = "/"
                    return self._send(302, "", "text/plain", h)
                with open(os.path.join(web, "index.html"), "rb") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            if u.path == "/api/auth":      # public: what should the login screen show?
                return self._send(200, {"authed": self._authed(), "configured": auth.configured,
                                        "can_setup": (not auth.configured) and self._local()})
            if not self._authed():
                return self._send(401, {"error": "unauthorized"})
            if u.path == "/api/state":
                return self._send(200, engine.state())
            if u.path == "/api/config":
                return self._send(200, engine.cfg)
            if u.path == "/api/actions":
                return self._send(200, api.describe())
            if u.path == "/api/templates":
                return self._send(200, engine.templates())
            if u.path == "/api/net":
                return self._send(200, {"bind": engine.cfg.get("bind", "127.0.0.1"), "active_bind": bind,
                                        "port": engine.cfg.get("port", 8765), "active_port": self.server.server_port,
                                        "user": auth.data.get("user", ""), "configured": auth.configured,
                                        "warning": warn})
            if u.path == "/api/events":
                since = int(q.get("since", ["0"])[0])
                with engine.lock:
                    return self._send(200, [e for e in engine.events if e["id"] > since])
            self._send(404, {"error": "not found"})

        # ---- POST
        def do_POST(self):
            if not self._host_ok() or not self._origin_ok():
                return self._send(403, {"error": "forbidden"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, {"error": "bad json"})
            p = urlparse(self.path).path
            try:
                if p == "/api/login":
                    ok, msg = auth.check(self._ip(), str(body.get("user", "")), str(body.get("pass", "")))
                    if not ok:
                        return self._send(401, {"error": msg})
                    return self._send(200, {"ok": True}, headers=self._session_cookie())
                if p == "/api/setup":      # first-run password creation, local machine only
                    if auth.configured or not self._local():
                        return self._send(403, {"error": "forbidden"})
                    return self._create_password(body)
                if p == "/api/logout":
                    with auth.lock:
                        auth.sessions.pop(self._cookie(), None)
                    return self._send(200, {"ok": True}, headers={"Set-Cookie": "dc_session=; Path=/; Max-Age=0"})
                if not self._authed():
                    return self._send(401, {"error": "unauthorized"})
                if p == "/api/password":
                    if auth.configured and not auth.check(self._ip(), auth.data["user"], str(body.get("old", "")))[0]:
                        return self._send(403, {"error": "Current password is wrong"})
                    return self._create_password(body)
                if p == "/api/net":
                    b = body.get("bind", "127.0.0.1")
                    if b not in ("127.0.0.1", "0.0.0.0"):
                        return self._send(400, {"error": "bind must be 127.0.0.1 or 0.0.0.0"})
                    if b == "0.0.0.0" and not auth.configured:
                        return self._send(400, {"error": "Set a password first"})
                    engine.cfg["bind"] = b
                    engine.cfg["port"] = max(1024, min(65535, int(body.get("port", 8765))))
                    engine.save()
                    return self._send(200, {"ok": True, "restart": True})
                if p == "/api/config":
                    new = dict(body)
                    for k in ("bind", "port"):       # network settings only change via /api/net
                        new[k] = engine.cfg.get(k, new.get(k))
                    engine.replace_config(new)
                    return self._send(200, {"ok": True})
                if p == "/api/test":
                    threading.Thread(target=engine.run_actions, args=(body.get("actions", []),), daemon=True).start()
                    return self._send(200, {"ok": True})
                if p == "/api/preview":
                    im = render.render_key(body).resize((96, 96))
                    b = io.BytesIO()
                    im.save(b, "PNG")
                    return self._send(200, b.getvalue(), "image/png")
                if p == "/api/profile":
                    engine.set_profile(body["name"])
                    return self._send(200, {"ok": True})
                if p == "/api/page":
                    engine.goto_page(body["name"])
                    return self._send(200, {"ok": True})
                if p == "/api/learn":
                    engine.learn = body.get("target") or None
                    return self._send(200, {"ok": True})
                if p == "/api/reload":
                    engine.load_plugins()
                    return self._send(200, {"ok": True})
                if p == "/api/pause":
                    engine.paused = bool(body.get("paused"))
                    return self._send(200, {"ok": True})
                if p == "/api/brightness":
                    engine.change_brightness(body["value"], False)
                    engine.save()
                    return self._send(200, {"ok": True})
                if p == "/api/open_accessibility":
                    import subprocess
                    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
                    return self._send(200, {"ok": True})
                if p == "/api/redraw":
                    engine.redraw()
                    return self._send(200, {"ok": True})
                if p == "/api/save_template":
                    nm = re.sub(r"[^A-Za-z0-9._ -]", "_", body["name"])[:50]
                    t = {"name": body["name"], "for": body.get("for", "any"), "control": body["control"]}
                    with open(os.path.join(paths.TEMPLATES, "user_" + nm + ".json"), "w", encoding="utf-8") as f:
                        json.dump(t, f, indent=2, ensure_ascii=False)
                    return self._send(200, {"ok": True})
                if p == "/api/upload":
                    name = re.sub(r"[^A-Za-z0-9._-]", "_", body["name"])[:60] or "image.png"
                    data = base64.b64decode(body["data"].split(",")[-1])
                    with open(os.path.join(paths.IMAGES, name), "wb") as f:
                        f.write(data)
                    return self._send(200, {"name": name})
            except Exception as e:
                return self._send(500, {"error": str(e)})
            self._send(404, {"error": "not found"})

        def _create_password(self, body):
            user = str(body.get("user", "")).strip()
            pw = str(body.get("pass", ""))
            if not user or len(pw) < 8:
                return self._send(400, {"error": "Username required and password must be at least 8 characters"})
            auth.set_password(user, pw)
            return self._send(200, {"ok": True}, headers=self._session_cookie())

    class Srv(ThreadingHTTPServer):
        daemon_threads = True

    for pt in range(port, port + 20):
        try:
            return Srv((bind, pt), H), pt, token, warn
        except OSError:
            continue
    raise RuntimeError("no free port")
