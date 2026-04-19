"""
One-shot OAuth helper to generate a new Google Calendar refresh_token.

Use this when the GitHub Action's Google Calendar step fails with
'invalid_client' or 'invalid_grant': you've rotated the client_secret in
Google Cloud Console, or the refresh token was revoked.

Steps:
  1. Open https://console.cloud.google.com/apis/credentials
  2. Pick (or create) an OAuth 2.0 Client ID of type "Desktop app".
     If you just rotated the secret, note the NEW Client ID + Client Secret.
     Make sure "Google Calendar API" is enabled for the project.
  3. Run this script:
         python scripts/get_google_refresh_token.py
  4. Paste the Client ID and Client Secret when prompted.
  5. A browser window opens → log in with the Google account that owns the
     calendar you want to read (danbmg555@gmail.com) → approve access.
  6. The script prints the three values to put in GitHub secrets:
         GOOGLE_CLIENT_ID
         GOOGLE_CLIENT_SECRET
         GOOGLE_REFRESH_TOKEN

No dependencies beyond the Python standard library.
"""
import http.server
import json
import socketserver
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/calendar.readonly"
REDIRECT_PORT = 8765
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"

received_code = {}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(q)
        if "code" in params:
            received_code["code"] = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h2>OK — you can close this tab and go back to the terminal.</h2>"
                .encode("utf-8")
            )
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, *args, **kwargs):
        pass


def main():
    print("Google OAuth refresh-token generator")
    print("-" * 40)
    client_id = input("Client ID: ").strip()
    client_secret = input("Client Secret: ").strip()
    if not client_id or not client_secret:
        sys.exit("Both Client ID and Client Secret are required.")

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(params)
    print(f"\nOpening browser to authorize… if it doesn't open, visit:\n  {url}\n")

    server = socketserver.TCPServer(("localhost", REDIRECT_PORT), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    webbrowser.open(url)

    # Wait for the redirect
    import time
    timeout = 180
    waited = 0
    while "code" not in received_code and waited < timeout:
        time.sleep(0.5)
        waited += 0.5
    server.shutdown()

    if "code" not in received_code:
        sys.exit("Timed out waiting for OAuth redirect.")

    code = received_code["code"]

    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(TOKEN_URL, data=data)
    with urllib.request.urlopen(req) as r:
        tok = json.loads(r.read().decode("utf-8"))

    refresh_token = tok.get("refresh_token")
    if not refresh_token:
        sys.exit(
            "No refresh_token returned. Likely cause: this account already "
            "granted access to this client. Revoke at "
            "https://myaccount.google.com/permissions and retry."
        )

    print("\n" + "=" * 60)
    print("Paste these three values into GitHub → Settings → Secrets → Actions")
    print("=" * 60)
    print(f"GOOGLE_CLIENT_ID     = {client_id}")
    print(f"GOOGLE_CLIENT_SECRET = {client_secret}")
    print(f"GOOGLE_REFRESH_TOKEN = {refresh_token}")
    print("=" * 60)


if __name__ == "__main__":
    main()
