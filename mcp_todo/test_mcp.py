"""Offline MCP protocol test — mocks TodoClient so no real auth/Graph calls happen."""
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
from mcp import types as mcp_types
from mcp.shared.session import SessionMessage


def _sm(obj: dict) -> SessionMessage:
    return SessionMessage(mcp_types.JSONRPCMessage.model_validate(obj))


async def run_tests() -> int:
    responses: dict[int, dict] = {}

    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "get_task_lists", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "create_task",
                    "arguments": {"list_id": "list-1", "title": "Buy milk",
                                  "due_date": "2026-04-01"}}},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "complete_task",
                    "arguments": {"list_id": "list-1", "task_id": "task-99"}}},
    ]

    send_in, recv_in   = anyio.create_memory_object_stream(max_buffer_size=32)
    send_out, recv_out = anyio.create_memory_object_stream(max_buffer_size=32)

    for m in messages:
        await send_in.send(_sm(m))

    mock_tc = MagicMock()
    mock_tc.start         = AsyncMock(return_value=None)
    mock_tc.close         = AsyncMock(return_value=None)
    mock_tc.get_task_lists = AsyncMock(return_value=[
        {"id": "list-1", "name": "Tasks"},
        {"id": "list-2", "name": "Groceries"},
    ])
    mock_tc.get_tasks      = AsyncMock(return_value=[])
    mock_tc.create_task    = AsyncMock(return_value="Task created (id=task-42): Buy milk")
    mock_tc.complete_task  = AsyncMock(return_value="Task task-99 marked as completed")

    EXPECTED = {1, 2, 3, 4, 5}

    with (
        patch("server.TodoClient", return_value=mock_tc),
        patch("server.make_token_getter", return_value=lambda: "fake-token"),
        patch.dict("os.environ", {"CLIENT_ID": "fake-id", "TENANT_ID": "common"}),
    ):
        import server
        server.todo_client = mock_tc

        async def run_server(cs: anyio.CancelScope):
            try:
                await server.app.run(recv_in, send_out,
                                     server.app.create_initialization_options())
            except Exception:
                pass
            finally:
                await send_out.aclose()
                cs.cancel()

        async def collect(cs: anyio.CancelScope):
            async with recv_out:
                async for sm in recv_out:
                    raw = sm.message.model_dump(by_alias=True, exclude_none=True)
                    mid = raw.get("id")
                    if mid is not None:
                        responses[mid] = raw
                    if EXPECTED.issubset(responses.keys()):
                        await send_in.aclose()
                        cs.cancel()
                        break

        with anyio.move_on_after(6) as root:
            async with anyio.create_task_group() as tg:
                tg.start_soon(run_server, root)
                tg.start_soon(collect,    root)

    # --- assertions ---
    passed = failed = 0

    def ok(msg):
        nonlocal passed; passed += 1; print(f"  PASS  {msg}")

    def fail(msg, detail=""):
        nonlocal failed; failed += 1
        print(f"  FAIL  {msg}" + (f"  ({detail})" if detail else ""))

    if 1 in responses:
        name = responses[1].get("result", {}).get("serverInfo", {}).get("name")
        ok(f"initialize  ->  {name}") if name == "todo-mcp" else fail("initialize name", name)
    else:
        fail("initialize (no response)")

    if 2 in responses:
        names = sorted(t["name"] for t in responses[2].get("result", {}).get("tools", []))
        expected = ["complete_task", "create_task", "get_task_lists", "get_tasks"]
        ok(f"tools/list  ->  {names}") if names == expected else fail("tools/list", str(names))
    else:
        fail("tools/list (no response)")

    if 3 in responses:
        text = responses[3].get("result", {}).get("content", [{}])[0].get("text", "")
        lists = json.loads(text)
        ok(f"get_task_lists  ->  {len(lists)} list(s)") if len(lists) == 2 else fail("get_task_lists count", text)
    else:
        fail("get_task_lists (no response)")

    if 4 in responses:
        text = responses[4].get("result", {}).get("content", [{}])[0].get("text", "")
        ok(f"create_task  ->  '{text}'") if "Task created" in text else fail("create_task", text)
    else:
        fail("create_task (no response)")

    if 5 in responses:
        text = responses[5].get("result", {}).get("content", [{}])[0].get("text", "")
        ok(f"complete_task  ->  '{text}'") if "completed" in text else fail("complete_task", text)
    else:
        fail("complete_task (no response)")

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(run_tests()))
