import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from auth import make_token_getter
from todo_client import TodoClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

CLIENT_ID  = os.getenv("CLIENT_ID", "")
TENANT_ID  = os.getenv("TENANT_ID", "common")

if not CLIENT_ID:
    sys.exit("CLIENT_ID is not set. Add it to mcp_todo/.env")

app = Server("todo-mcp")
todo_client: TodoClient | None = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_task_lists",
            description="Return all Microsoft To Do task lists for the authenticated user.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_tasks",
            description="Return all tasks inside a specific To Do list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {
                        "type": "string",
                        "description": "The ID of the task list (from get_task_lists)",
                    },
                },
                "required": ["list_id"],
            },
        ),
        Tool(
            name="create_task",
            description="Create a new task in a To Do list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {
                        "type": "string",
                        "description": "The ID of the target task list",
                    },
                    "title": {
                        "type": "string",
                        "description": "Title of the task",
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Optional due date in YYYY-MM-DD format",
                    },
                },
                "required": ["list_id", "title"],
            },
        ),
        Tool(
            name="complete_task",
            description="Mark an existing task as completed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_id": {
                        "type": "string",
                        "description": "The ID of the task list containing the task",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "The ID of the task to complete (from get_tasks)",
                    },
                },
                "required": ["list_id", "task_id"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    assert todo_client is not None, "TodoClient not initialised"

    if name == "get_task_lists":
        result = await todo_client.get_task_lists()
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "get_tasks":
        result = await todo_client.get_tasks(list_id=arguments["list_id"])
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    if name == "create_task":
        result = await todo_client.create_task(
            list_id=arguments["list_id"],
            title=arguments["title"],
            due_date=arguments.get("due_date"),
        )
        return [TextContent(type="text", text=result)]

    if name == "complete_task":
        result = await todo_client.complete_task(
            list_id=arguments["list_id"],
            task_id=arguments["task_id"],
        )
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    global todo_client

    token_getter = make_token_getter(client_id=CLIENT_ID, tenant_id=TENANT_ID)
    todo_client = TodoClient(token_getter=token_getter)

    # Authentication happens here — device flow prints to stderr on first run
    await todo_client.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await todo_client.close()


if __name__ == "__main__":
    asyncio.run(main())
