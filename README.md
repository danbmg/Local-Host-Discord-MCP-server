# Discord MCP Server (local, stdio)

A local [Model Context Protocol](https://modelcontextprotocol.io) server that exposes Discord actions as tools over **stdio transport** — no HTTP server required.

---

## Tools

| Tool | Description |
|---|---|
| `send_message` | Send a text message to a channel |
| `read_messages` | Fetch recent messages from a channel |
| `list_channels` | List all channels in a guild/server |
| `add_reaction` | Add an emoji reaction to a message |

---

## Requirements

- Python 3.11+
- A Discord **Bot token** with the following permissions:
  - `Read Messages / View Channels`
  - `Send Messages`
  - `Add Reactions`
  - `Read Message History`
- The bot must be invited to your server (guild).
- **Message Content Intent** must be enabled in the Discord Developer Portal (Bot → Privileged Gateway Intents).

---

## Setup

### 1. Clone / open the project

```
cd mcp_discord
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure credentials

Edit `mcp_discord/.env`:

```env
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=your-guild-id-here
```

- **DISCORD_TOKEN** — found in the Discord Developer Portal under your application → Bot → Token.
- **DISCORD_GUILD_ID** — right-click your server in Discord → "Copy Server ID" (Developer Mode must be on: Settings → Advanced → Developer Mode).

### 4. Run the server manually (optional smoke test)

```bash
python server.py
```

The process will connect to Discord, then wait on stdin for MCP JSON-RPC messages. Press `Ctrl+C` to stop.

---

## Connecting to Claude Desktop

Open your Claude Desktop config file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add an entry under `mcpServers`:

```json
{
  "mcpServers": {
    "discord": {
      "command": "C:\\path\\to\\your\\.venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\mcp_discord\\server.py"],
      "env": {}
    }
  }
}
```

Replace both paths with the absolute paths on your machine, then **restart Claude Desktop**. The Discord tools will appear in the tool picker.

### Windows path example

```json
{
  "mcpServers": {
    "discord": {
      "command": "C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_discord\\.venv\\Scripts\\python.exe",
      "args": ["C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_discord\\server.py"]
    }
  }
}
```

---

## Connecting to Claude Code (CLI)

```bash
claude mcp add discord \
  --command "C:/delivery/Local-Host-Discord-MCP-server/mcp_discord/.venv/Scripts/python.exe" \
  --args "C:/delivery/Local-Host-Discord-MCP-server/mcp_discord/server.py"
```

Or edit `~/.claude/settings.json` directly:

```json
{
  "mcpServers": {
    "discord": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/mcp_discord/server.py"]
    }
  }
}
```

---

## Project structure

```
mcp_discord/
├── server.py          # MCP server — tool definitions and handlers
├── discord_client.py  # discord.py wrapper with error handling
├── .env               # DISCORD_TOKEN, DISCORD_GUILD_ID (not committed)
└── requirements.txt   # mcp, discord.py, python-dotenv
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `DISCORD_TOKEN is not set` | Fill in `.env` and make sure the working directory is `mcp_discord/` |
| `Missing permissions` errors | Re-invite the bot with the required permissions |
| `Message Content Intent` errors | Enable the intent in the Discord Developer Portal |
| Server exits immediately | Check that the venv Python is used, not the system Python |
| `ModuleNotFoundError: mcp` | Run `pip install -r requirements.txt` inside the venv |
