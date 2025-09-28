#!/usr/bin/env python3
"""Interactive helper to generate Twitter OAuth 2.0 user tokens with PKCE."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

AUTH_URL = "https://twitter.com/i/oauth2/authorize"
TOKEN_URL = "https://api.twitter.com/2/oauth2/token"

DEFAULT_SCOPE = "tweet.write offline.access"
DEFAULT_PORT = 8079
DEFAULT_REDIRECT_PATH = "/callback"


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = _b64url_encode(secrets.token_bytes(32))
    challenge = _b64url_encode(hashlib.sha256(verifier.encode()).digest())
    return verifier, challenge


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Simple handler that captures the OAuth authorization response."""

    server_version = "TwitterOAuthSetup/1.0"

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler signature)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != self.server.expected_path:  # type: ignore[attr-defined]
            self.send_error(HTTPStatus.NOT_FOUND, "Unknown path")
            return

        query = urllib.parse.parse_qs(parsed.query)
        code = query.get("code", [None])[0]
        state = query.get("state", [None])[0]
        error = query.get("error", [None])[0]

        payload = {
            "code": code,
            "state": state,
            "error": error,
            "raw_query": parsed.query,
        }
        self.server.oauth_result = payload  # type: ignore[attr-defined]
        self.server.oauth_event.set()  # type: ignore[attr-defined]

        body = """
        <html>
          <head><title>Twitter OAuth</title></head>
          <body>
            <h2>Authorization Received</h2>
            <p>You can return to the CLI — the authorization code has been captured.</p>
          </body>
        </html>
        """.strip()
        body_bytes = body.encode()

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, format, *args):  # noqa: A003 - match base signature
        # Silence default logging to avoid leaking secrets in console.
        return


def _start_callback_server(port: int, path: str, event: threading.Event):
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, _OAuthCallbackHandler)
    httpd.expected_path = path  # type: ignore[attr-defined]
    httpd.oauth_event = event  # type: ignore[attr-defined]
    httpd.oauth_result = None  # type: ignore[attr-defined]

    thread = threading.Thread(target=httpd.serve_forever, name="OAuthCallbackServer", daemon=True)
    thread.start()
    return httpd, thread


def _build_authorize_url(*, client_id: str, redirect_uri: str, scope: str, state: str, code_challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict:
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
    response = requests.post(TOKEN_URL, data=data, auth=auth, timeout=15)
    response.raise_for_status()
    return response.json()


def persist_tokens(tokens: dict, output_path: str | None):
    pretty = json.dumps(tokens, indent=2)
    print("\n=== OAuth Tokens ===")
    print(pretty)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(pretty)
        os.chmod(output_path, 0o600)
        print(f"\nSaved token response to {output_path} (permissions set to 600).")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive Twitter OAuth 2.0 token helper")
    parser.add_argument("--client-id", help="Twitter app Client ID (required)")
    parser.add_argument("--client-secret", help="Twitter app Client Secret (required)")
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help=f"OAuth scopes to request (default: '{DEFAULT_SCOPE}')")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Local port to bind for callback (default: {DEFAULT_PORT})")
    parser.add_argument("--redirect-path", default=DEFAULT_REDIRECT_PATH, help=f"Callback path (default: {DEFAULT_REDIRECT_PATH})")
    parser.add_argument("--output", help="Optional file path to write the token response JSON")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the authorization URL automatically in the browser")
    return parser.parse_args()


def main():
    args = parse_args()

    client_id = args.client_id or os.environ.get("TWITTER_CLIENT_ID")
    client_secret = args.client_secret or os.environ.get("TWITTER_CLIENT_ID_SECRET")

    if not client_id:
        client_id = input("Client ID: ").strip()
    if not client_secret:
        client_secret = input("Client Secret: ").strip()

    scope = args.scope.strip()

    if not client_id or not client_secret:
        print("Client ID and Client Secret are required.")
        return 1

    redirect_uri = f"http://127.0.0.1:{args.port}{args.redirect_path}"
    print(f"Using redirect URI: {redirect_uri}")

    verifier, challenge = _generate_pkce_pair()
    state = _b64url_encode(secrets.token_bytes(16))
    authorize_url = _build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=challenge,
    )

    event = threading.Event()
    server, thread = _start_callback_server(args.port, args.redirect_path, event)
    print("Listening for OAuth callback...")

    print("\nOpen this URL in your browser to authorize the app:\n")
    print(authorize_url)

    if not args.no_browser:
        try:
            opened = webbrowser.open(authorize_url)
        except Exception:
            opened = False
        if not opened:
            print("(Could not auto-launch a browser. Please copy the URL above into your browser manually.)")

    timeout_seconds = 300
    print(f"Waiting up to {timeout_seconds} seconds for authorization...")
    start = time.time()
    try:
        while not event.wait(timeout=1):
            elapsed = int(time.time() - start)
            print(f"  Still waiting ({elapsed}s elapsed)...", end="\r", flush=True)
            if elapsed >= timeout_seconds:
                print("\nTimed out waiting for authorization. Please retry.")
                return 1
    finally:
        server.shutdown()
        thread.join(timeout=2)

    result = server.oauth_result  # type: ignore[attr-defined]
    if not result:
        print("No authorization result captured. Please retry.")
        return 1

    if result.get("error"):
        print(f"Authorization returned error: {result['error']}")
        return 1

    if result.get("state") != state:
        print("State mismatch. Aborting for safety.")
        return 1

    code = result.get("code")
    if not code:
        print("Authorization code missing from callback. Inspect the redirect URL and retry.")
        return 1

    print("\nAuthorization code received. Exchanging for tokens...")
    try:
        tokens = exchange_code_for_tokens(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=verifier,
        )
    except requests.HTTPError as exc:
        print(f"Token exchange failed: {exc.response.status_code} {exc.response.text}")
        return 1

    persist_tokens(tokens, args.output)
    print("\nExport the access and refresh tokens as environment variables for the bot, for example:\n")
    if access_token := tokens.get("access_token"):
        print(f"  export TWITTER_OAUTH2_ACCESS_TOKEN='{access_token}'")
    if refresh_token := tokens.get("refresh_token"):
        print(f"  export TWITTER_OAUTH2_REFRESH_TOKEN='{refresh_token}'")
    print(f"  export TWITTER_CLIENT_ID='{client_id}'")
    print(f"  export TWITTER_CLIENT_ID_SECRET='{client_secret}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
