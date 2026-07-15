from __future__ import annotations
import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Any
from ..domain.models import Settings
from ..storage.secrets import load_secret, delete_secret, save_secret


class OAuthCallbackServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], RequestHandlerClass: type[BaseHTTPRequestHandler]):
        super().__init__(server_address, RequestHandlerClass)
        self.oauth_result: Dict[str, str] = {}
        self.oauth_ready = threading.Event()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: OAuthCallbackServer

    def do_GET(self) -> None:
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        self.server.oauth_result["code"] = q.get("code", [""])[0]
        self.server.oauth_result["state"] = q.get("state", [""])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<h2>Authentication completed. You may close this tab.</h2>"
        )
        self.server.oauth_ready.set()

    def log_message(self, *args: Any) -> None:
        pass


class GoogleOAuth:
    def __init__(self, settings: Settings, on_refresh):
        self.s = settings
        self.on_refresh = on_refresh
        self.access = ""
        self.expiry = 0
        self._lock = threading.Lock()

    def token(self) -> str:
        if self.access and time.time() < self.expiry:
            return self.access

        with self._lock:
            if self.access and time.time() < self.expiry:
                return self.access

            refresh_token = load_secret("refresh_token")
            if refresh_token:
                try:
                    return self._exchange(
                        {
                            "client_id": self.s.client_id,
                            "refresh_token": refresh_token,
                            "grant_type": "refresh_token",
                        }
                    )
                except Exception:
                    pass
            return self._interactive()

    def _exchange(self, data):
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            urllib.parse.urlencode(data).encode(),
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            payload = json.load(res)
        self.access = payload["access_token"]
        self.expiry = time.time() + max(60, int(payload.get("expires_in", 3600)) - 60)
        if payload.get("refresh_token"):
            save_secret("refresh_token", payload["refresh_token"])
            self.on_refresh(self.s)
        return self.access

    def _interactive(self):
        if not self.s.client_id:
            raise RuntimeError("Configure the Google OAuth Desktop Client ID first.")
        verifier = (
            base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
        )
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        state = secrets.token_urlsafe(24)

        server = OAuthCallbackServer(("127.0.0.1", 0), OAuthCallbackHandler)
        redirect = f"http://127.0.0.1:{server.server_port}/"
        thread = threading.Thread(target=server.handle_request, daemon=True)
        thread.start()
        params = {
            "client_id": self.s.client_id,
            "redirect_uri": redirect,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/drive",
            "access_type": "offline",
            "prompt": "consent",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
        webbrowser.open(
            "https://accounts.google.com/o/oauth2/v2/auth?"
            + urllib.parse.urlencode(params)
        )
        if not server.oauth_ready.wait(300):
            server.server_close()
            raise TimeoutError("Google sign-in timed out")
        server.server_close()

        result_state = server.oauth_result.get("state")
        result_code = server.oauth_result.get("code")

        if result_state != state or not result_code:
            raise RuntimeError("OAuth cancelled or state validation failed")
        return self._exchange(
            {
                "code": result_code,
                "client_id": self.s.client_id,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            }
        )

    def logout(self) -> None:
        self.access = ""
        self.expiry = 0
        delete_secret("refresh_token")
