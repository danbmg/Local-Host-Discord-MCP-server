import asyncio
import logging
import os
import sys
import traceback

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from discord_client import DiscordClient

# ---------------------------------------------------------------------------
# Logging — MUST go to stderr (stdout is reserved for the MCP JSON-RPC stream).
# Claude Desktop/Code captures stderr and shows it in the MCP logs panel.
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=os.getenv("MCP_LOG_LEVEL", "INFO"),
    stream=sys.stderr,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
# discord.py is noisy at INFO; keep it at WARNING unless explicitly raised.
logging.getLogger("discord").setLevel(
    os.getenv("DISCORD_LOG_LEVEL", "WARNING")
)
log = logging.getLogger("mcp_discord.server")

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")

if not DISCORD_TOKEN:
    log.error("DISCORD_TOKEN is not set. Add it to mcp_discord/.env")
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
                        "description": "Number of messages to retrieve (1-100, default 10)",
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
                        "description": "Unicode emoji (e.g. '\U0001f44d') or custom emoji name (e.g. ':my_emoji:')",
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
    log.info("tool call: %s args=%s", name, arguments)

    if discord_client is None:
        log.error("tool call '%s' arrived before Discord client was initialised", name)
        return [TextContent(
            type="text",
            text="Error: Discord client not initialised yet. Check MCP server logs.",
        )]

    if not discord_client._ready:
        log.warning("tool '%s' called but Discord gateway is not ready", name)
        return [TextContent(
            type="text",
            text="Error: Discord gateway not connected. Check MCP server logs.",
        )]

    try:
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
    except Exception:
        tb = traceback.format_exc()
        log.exception("tool '%s' raised", name)
        return [TextContent(
            type="text",
            text=f"Error: tool '{name}' raised an exception:\n{tb}",
        )]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    global discord_client
    log.info("Booting discord-mcp server (pid=%s)", os.getpid())
    discord_client = DiscordClient(token=DISCORD_TOKEN)

    try:
        await discord_client.start()
    except Exception as exc:
        log.error("Failed to connect to Discord: %r", exc)
        raise

    log.info("Discord ready - entering MCP stdio loop")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    except Exception:
        log.exception("MCP loop crashed")
        raise
    finally:
        log.info("Shutting down discord client")
        await discord_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Interrupted by user")
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)
