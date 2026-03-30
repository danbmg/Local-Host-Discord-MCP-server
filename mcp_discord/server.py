import asyncio
import os
import sys

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from discord_client import DiscordClient

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")

if not DISCORD_TOKEN:
    sys.exit("DISCORD_TOKEN is not set. Add it to mcp_discord/.env")

app = Server("discord-mcp")
discord_client: DiscordClient | None = None


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_message",
            description="Send a text message to a Discord channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Numeric ID of the Discord channel",
                    },
                    "content": {
                        "type": "string",
                        "description": "Message text to send (max 2000 chars)",
                    },
                },
                "required": ["channel_id", "content"],
            },
        ),
        Tool(
            name="read_messages",
            description="Fetch recent messages from a Discord channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Numeric ID of the Discord channel",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to retrieve (1–100, default 10)",
                        "default": 10,
                    },
                },
                "required": ["channel_id"],
            },
        ),
        Tool(
            name="list_channels",
            description="List all channels in a Discord guild/server.",
            inputSchema={
                "type": "object",
                "properties": {
                    "guild_id": {
                        "type": "string",
                        "description": (
                            "Numeric ID of the Discord guild. "
                            "Defaults to DISCORD_GUILD_ID from .env if omitted."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="add_reaction",
            description="Add an emoji reaction to a Discord message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Numeric ID of the Discord channel",
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Numeric ID of the message to react to",
                    },
                    "emoji": {
                        "type": "string",
                        "description": "Unicode emoji (e.g. '👍') or custom emoji name (e.g. ':my_emoji:')",
                    },
                },
                "required": ["channel_id", "message_id", "emoji"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool call handler
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    assert discord_client is not None, "Discord client not initialised"

    if name == "send_message":
        result = await discord_client.send_message(
            channel_id=arguments["channel_id"],
            content=arguments["content"],
        )
        return [TextContent(type="text", text=result)]

    if name == "read_messages":
        limit = int(arguments.get("limit", 10))
        messages = await discord_client.read_messages(
            channel_id=arguments["channel_id"],
            limit=limit,
        )
        text = "\n".join(messages) if messages else "(no messages)"
        return [TextContent(type="text", text=text)]

    if name == "list_channels":
        guild_id = arguments.get("guild_id") or DISCORD_GUILD_ID
        if not guild_id:
            return [TextContent(
                type="text",
                text="Error: guild_id not provided and DISCORD_GUILD_ID is not set in .env",
            )]
        channels = await discord_client.list_channels(guild_id=guild_id)
        import json
        return [TextContent(type="text", text=json.dumps(channels, indent=2))]

    if name == "add_reaction":
        result = await discord_client.add_reaction(
            channel_id=arguments["channel_id"],
            message_id=arguments["message_id"],
            emoji=arguments["emoji"],
        )
        return [TextContent(type="text", text=result)]

    return [TextContent(type="text", text=f"Error: Unknown tool '{name}'")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    global discord_client
    discord_client = DiscordClient(token=DISCORD_TOKEN)
    await discord_client.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await discord_client.close()


if __name__ == "__main__":
    asyncio.run(main())
