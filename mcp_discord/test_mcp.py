"""
Offline MCP protocol test.
Uses anyio memory streams to drive the MCP stack without needing a real
Discord connection or subprocess.
"""
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
from mcp import types as mcp_types
from mcp.shared.session import SessionMessage


def make_session_message(obj: dict) -> SessionMessage:
    msg = mcp_types.JSONRPCMessage.model_validate(obj)
    return SessionMessage(msg)


async def run_tests() -> int:
    responses: dict[int, dict] = {}

    inbound_messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "send_message",
                "arguments": {"channel_id": "123456789", "content": "hello world"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "list_channels",
                "arguments": {},           # no guild_id, DISCORD_GUILD_ID unset
            },
        },
    ]

    # Build anyio memory stream pairs
    # client -> server
    client_to_server_send, client_to_server_recv = anyio.create_memory_object_stream(
        max_buffer_size=32
    )
    # server -> client
    server_to_client_send, server_to_client_recv = anyio.create_memory_object_stream(
        max_buffer_size=32
    )

    # Feed all inbound messages (keep the send side open until server is cancelled)
    for obj in inbound_messages:
        await client_to_server_send.send(make_session_message(obj))

    # Mock discord client
    mock_dc = MagicMock()
    mock_dc.start         = AsyncMock(return_value=None)
    mock_dc.close         = AsyncMock(return_value=None)
    mock_dc.send_message  = AsyncMock(return_value="Message sent (id=999)")
    mock_dc.read_messages = AsyncMock(
        return_value=["[2026-01-01 00:00:00 UTC] Bot: hello"]
    )
    mock_dc.list_channels = AsyncMock(return_value=[])
    mock_dc.add_reaction  = AsyncMock(return_value="Reaction :+1: added to message 42")

    with (
        patch("server.DiscordClient", return_value=mock_dc),
        patch.dict("os.environ", {"DISCORD_TOKEN": "fake", "DISCORD_GUILD_ID": ""}),
        patch("server.DISCORD_GUILD_ID", ""),   # override the module-level var set by load_dotenv
    ):
        import server

        server.discord_client = None

        EXPECTED_IDS = {1, 2, 3, 4}

        server.discord_client = mock_dc

        async def run_server(cancel_scope: anyio.CancelScope):
            try:
                await server.app.run(
                    client_to_server_recv,
                    server_to_client_send,
                    server.app.create_initialization_options(),
                )
            except Exception:
                pass
            finally:
                await server_to_client_send.aclose()
                cancel_scope.cancel()

        async def collect_responses(cancel_scope: anyio.CancelScope):
            async with server_to_client_recv:
                async for session_msg in server_to_client_recv:
                    raw = session_msg.message.model_dump(by_alias=True, exclude_none=True)
                    mid = raw.get("id")
                    if mid is not None:
                        responses[mid] = raw
                    if EXPECTED_IDS.issubset(responses.keys()):
                        # All expected responses collected — stop the server
                        await client_to_server_send.aclose()
                        cancel_scope.cancel()
                        break

        with anyio.move_on_after(6) as root_scope:
            async with anyio.create_task_group() as tg:
                tg.start_soon(run_server,       root_scope)
                tg.start_soon(collect_responses, root_scope)

    # ---------- assertions ----------
    passed = failed = 0

    def ok(label: str):
        nonlocal passed
        passed += 1
        print(f"  PASS  {label}")

    def fail(label: str, detail: str = ""):
        nonlocal failed
        failed += 1
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))

    # 1. initialize
    if 1 in responses:
        info = responses[1].get("result", {}).get("serverInfo", {})
        if info.get("name") == "discord-mcp":
            ok(f"initialize  ->  serverInfo={info}")
        else:
            fail("initialize serverInfo.name wrong", str(info))
    else:
        fail("initialize (no response)", str(list(responses.keys())))

    # 2. tools/list — must contain all 4 tools
    if 2 in responses:
        tools = responses[2].get("result", {}).get("tools", [])
        names = {t["name"] for t in tools}
        expected = {"send_message", "read_messages", "list_channels", "add_reaction"}
        missing = expected - names
        if not missing:
            ok(f"tools/list  ->  {sorted(names)}")
        else:
            fail("tools/list missing tools", str(missing))
    else:
        fail("tools/list (no response)")

    # 3. send_message tool call
    if 3 in responses:
        content = responses[3].get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        if "Message sent" in text:
            ok(f"send_message  ->  '{text}'")
        else:
            fail("send_message unexpected result", text or repr(responses[3]))
    else:
        fail("send_message call (no response)")

    # 4. list_channels without guild_id → error string
    if 4 in responses:
        content = responses[4].get("result", {}).get("content", [])
        text = content[0].get("text", "") if content else ""
        if "guild_id not provided" in text:
            ok(f"list_channels (no guild_id)  ->  '{text}'")
        else:
            fail("list_channels unexpected result", text or repr(responses[4]))
    else:
        fail("list_channels call (no response)")

    print()
    print(f"Results: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))
