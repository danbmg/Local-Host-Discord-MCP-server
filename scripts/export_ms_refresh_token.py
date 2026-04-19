"""
Extract the Microsoft refresh_token from mcp_todo/token_cache.json.

Usage (from the repo root):
    python scripts/export_ms_refresh_token.py

Copy the printed refresh_token value into GitHub → repo Settings → Secrets and
variables → Actions → MS_REFRESH_TOKEN.

The cache file is written by mcp_todo/auth.py after a successful device-flow
login. If the refresh_token shown here stops working, delete
mcp_todo/token_cache.json and re-run the mcp_todo MCP server (or run
mcp_todo/test_mcp.py) to trigger a fresh device-flow login, then re-run this
script.
"""
import json
import os
import sys

CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mcp_todo",
    "token_cache.json",
)

if not os.path.exists(CACHE):
    sys.exit(f"Cache not found: {CACHE}\nRun the mcp_todo server once to create it.")

with open(CACHE, encoding="utf-8") as f:
    data = json.load(f)

rts = data.get("RefreshToken", {})
if not rts:
    sys.exit("No RefreshToken entries in cache. Re-run device-flow auth.")

# MSAL may keep multiple entries (one per client/scope); pick the newest.
entries = list(rts.values())
entries.sort(key=lambda e: int(e.get("last_modification_time", "0")), reverse=True)
secret = entries[0].get("secret")
if not secret:
    sys.exit("RefreshToken entry has no 'secret' field.")

print("=" * 60)
print("Copy the value below into GitHub secret MS_REFRESH_TOKEN")
print("=" * 60)
print(secret)
print("=" * 60)
print(f"(Also verify MS_CLIENT_ID matches: {entries[0].get('client_id', '(unknown)')})")
