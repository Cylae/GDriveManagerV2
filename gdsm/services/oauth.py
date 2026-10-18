"""Desktop OAuth with PKCE and serialized token refresh and logout."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable, Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ..domain.models import Settings
from ..storage.secrets import delete_secret, load_secret, save_secret


class OAuthCallbackServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        state: str,
    ):
        super().__init__(server_address, handler)
        self.oauth_result: dict[str, str] = {}
        self.oauth_ready = threading.Event()
        self.expected_state = state
        self.result_lock = threading.Lock()


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    server: OAuthCallbackServer

    def do_GET(self) -> None:
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        if url.path != "/" or query.get("state", [""])[0] != self.server.expected_state:
            self.send_error(400, "Invalid OAuth callback")
            return
        with self.server.result_lock:
            if self.server.oauth_ready.is_set():
                self.send_error(409, "OAuth callback already received")
                return
            self.server.oauth_result = {
                key: query.get(key, [""])[0] for key in ("code", "state", "error")
            }
            self.server.oauth_ready.set()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>Sign-in response received. You may close this tab.</h2>")

    def log_message(self, *args: Any) -> None:
        # Callback URLs contain authorization codes and must never be logged.
        pass


class GoogleOAuth:
    def __init__(self, settings: Settings, on_refresh: Callable[[Settings], None]):
        self.s = settings
        self.on_refresh = on_refresh
        self.access = ""
        self.expiry = 0.0
        self._lock = threading.Lock()
        self._refresh_lock = threading.Lock()

    def token(self) -> str:
        """Return a cached token or allow exactly one worker to authorize."""
        with self._lock:
            if self.access and time.time() < self.expiry:
                return self.access
        with self._refresh_lock:
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
                except urllib.error.HTTPError as error:
                    # Only a revoked grant requires a browser. Outages propagate.
                    if error.code != 400:
                        raise
                    try:
                        payload = json.loads(error.read())
                    finally:
                        error.close()
                    if (
                        not isinstance(payload, dict)
                        or payload.get("error") != "invalid_grant"
                    ):
                        raise
            return self._interactive()

    def _exchange(self, data: Mapping[str, str]) -> str:
        request = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            urllib.parse.urlencode(data).encode(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("access_token"), str)
            or not payload["access_token"]
        ):
            raise ValueError("Invalid OAuth token response")
        lifetime = float(payload.get("expires_in", 3600))
        if not 0 < lifetime < float("inf"):
            raise ValueError("Invalid OAuth token lifetime")
        access_token = payload["access_token"]
        expiry = time.time() + max(0.0, lifetime - min(60.0, lifetime / 10))
        refresh = payload.get("refresh_token")
        if refresh:
            if not isinstance(refresh, str):
                raise ValueError("Invalid OAuth refresh token")
            save_secret("refresh_token", refresh)
            self.on_refresh(self.s)
        with self._lock:
            self.access = access_token
            self.expiry = expiry
        return access_token

    def _interactive(self) -> str:
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
        server = OAuthCallbackServer(("127.0.0.1", 0), OAuthCallbackHandler, state)
        redirect = f"http://127.0.0.1:{server.server_port}/"
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
        )
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
        try:
            if not webbrowser.open(
                "https://accounts.google.com/o/oauth2/v2/auth?"
                + urllib.parse.urlencode(params)
            ):
                raise RuntimeError("Could not open a browser for Google sign-in")
            if not server.oauth_ready.wait(300):
                raise TimeoutError("Google sign-in timed out")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        result = server.oauth_result
        if (
            result.get("state") != state
            or not result.get("code")
            or result.get("error")
        ):
            raise RuntimeError("OAuth cancelled or state validation failed")
        return self._exchange(
            {
                "code": result["code"],
                "client_id": self.s.client_id,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            }
        )

    def logout(self) -> None:
        """Wait for any refresh, then clear cached and persistent credentials."""
        with self._refresh_lock:
            with self._lock:
                self.access = ""
                self.expiry = 0.0
            delete_secret("refresh_token")
