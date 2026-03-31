"""
MSAL device-flow authentication for Microsoft Graph.

First run  : opens a device-flow prompt on stderr (user visits URL + enters code).
Later runs : silently refreshes the access token from token_cache.json.
"""
import os
import sys
from functools import partial

import msal

CACHE_FILE = os.path.join(os.path.dirname(__file__), "token_cache.json")
SCOPES = ["Tasks.ReadWrite"]  # offline_access is added automatically by MSAL


def get_token(client_id: str, tenant_id: str) -> str:
    """Return a valid access token, authenticating via device flow if needed.

    This function is synchronous (MSAL is sync-only). Call it from async
    code via asyncio.get_event_loop().run_in_executor(None, get_token, ...).
    """
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache.deserialize(f.read())

    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    result = None

    # Try silent refresh first (uses cached refresh token)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    # Fall back to device flow (first run or cache cleared)
    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(
                f"Failed to initiate device flow: {flow.get('error_description', flow)}"
            )
        # Print instructions to stderr so they don't pollute the MCP stdout stream
        print(flow["message"], file=sys.stderr, flush=True)
        result = app.acquire_token_by_device_flow(flow)

    # Persist updated cache (new tokens / refreshed tokens)
    if cache.has_state_changed:
        with open(CACHE_FILE, "w") as f:
            f.write(cache.serialize())

    if "access_token" not in result:
        raise RuntimeError(
            f"Authentication failed: {result.get('error_description', result.get('error', result))}"
        )

    return result["access_token"]


def make_token_getter(client_id: str, tenant_id: str):
    """Return a zero-argument callable that always returns a fresh token."""
    return partial(get_token, client_id=client_id, tenant_id=tenant_id)
