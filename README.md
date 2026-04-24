# Local MCP Servers — Discord, Microsoft To Do & Otter.ai

Local [Model Context Protocol](https://modelcontextprotocol.io) servers that expose Discord, Microsoft To Do and Otter.ai actions as tools over **stdio transport** — no HTTP server required.

---

## Global architecture

Each server is a standalone Python process launched by Claude Desktop (or Claude Code). Claude sends JSON-RPC messages over stdin/stdout; the server translates them into API calls.

```
Claude (Desktop / Code)
    │
    ├─► mcp_discord/server.py  ──►  Bot "Claude_MCP"  ──►  Discord
    │
    ├─► mcp_todo/server.py     ──►  Microsoft Graph API  ──►  Microsoft To Do
    │
    └─► mcp-otter/run_otter.py ──►  Otter.ai API  ──►  Meeting transcripts
```

No network port is opened. Each server lives only as long as its parent Claude session.

---

## mcp_discord — Discord tools

### Tools

| Tool | Description |
|---|---|
| `send_message` | Send a text message to a channel |
| `read_messages` | Fetch recent messages from a channel |
| `list_channels` | List all channels in a guild/server |
| `add_reaction` | Add an emoji reaction to a message |

### Requirements

- Python 3.11+
- A Discord **Bot token** with the following permissions:
  - `Read Messages / View Channels`
  - `Send Messages`
  - `Add Reactions`
  - `Read Message History`
- The bot must be invited to your server (guild).
- **Message Content Intent** must be enabled in the Discord Developer Portal (Bot → Privileged Gateway Intents).

### Setup

**1. Create a virtual environment and install dependencies**

```bat
cd mcp_discord

:: Find the uv-managed Python (adjust path if different)
set PY=C:\Users\%USERNAME%\AppData\Roaming\uv\python\cpython-3.14.3-windows-x86_64-none\python.exe
%PY% -m venv .venv

.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure credentials** — edit `mcp_discord/.env`:

```env
DISCORD_TOKEN=your-bot-token-here
DISCORD_GUILD_ID=your-guild-id-here
```

- **DISCORD_TOKEN** — Discord Developer Portal → your app → Bot → Token.
- **DISCORD_GUILD_ID** — right-click your server in Discord → "Copy Server ID" (requires Developer Mode: Settings → Advanced → Developer Mode).

**3. Smoke test**

```bat
cd mcp_discord
.venv\Scripts\python.exe server.py
```

The process connects to Discord then waits on stdin. Press `Ctrl+C` to stop.

---

## mcp_todo — Microsoft To Do tools

### Tools

| Tool | Description |
|---|---|
| `get_task_lists` | Return all task lists for the authenticated user |
| `get_tasks` | Return all tasks in a specific list |
| `create_task` | Create a new task (optional due date) |
| `complete_task` | Mark a task as completed |

### Requirements

- Python 3.11+
- An **Azure App Registration** with:
  - Platform: **Mobile and desktop applications** (public client)
  - Delegated API permission: `Tasks.ReadWrite` (Microsoft Graph)
  - Redirect URI: `https://login.microsoftonline.com/common/oauth2/nativeclient`
- `TENANT_ID` can stay `common` for personal Microsoft accounts, or be set to your tenant ID for work/school accounts.

> **CLIENT_SECRET** is stored in `.env` for reference but is not used by the device flow
> (which is a public-client flow). It can be left as-is.

### Setup

**1. Create a virtual environment and install dependencies**

```bat
cd mcp_todo

set PY=C:\Users\%USERNAME%\AppData\Roaming\uv\python\cpython-3.14.3-windows-x86_64-none\python.exe
%PY% -m venv .venv

.venv\Scripts\activate
pip install -r requirements.txt
```

**2. Configure credentials** — edit `mcp_todo/.env`:

```env
CLIENT_ID=your-azure-app-client-id-here
CLIENT_SECRET=your-azure-app-client-secret-here
TENANT_ID=common
```

**3. First-run authentication**

On the very first launch the server prints a device-flow message to **stderr**:

```
To sign in, use a web browser to open https://microsoft.com/devicelogin
and enter the code XXXXXXXX to authenticate.
```

Open the URL, enter the code, sign in with your Microsoft account, grant the `Tasks.ReadWrite` permission. The token is saved to `mcp_todo/token_cache.json` and refreshed automatically on subsequent runs.

**4. Smoke test**

```bat
cd mcp_todo
.venv\Scripts\python.exe server.py
```

---

## mcp-otter — Otter.ai transcript tools

Third-party MCP server by [Darren Zal](https://github.com/DarrenZal/otter-mcp) (MIT License), vendored in [mcp-otter/](mcp-otter/) and wrapped with a local `.env` loader ([run_otter.py](mcp-otter/run_otter.py)) to match the credentials pattern used by the other two servers.

### Tools

| Tool | Description |
|---|---|
| `otter_search` | Full-text search across all your Otter transcripts |
| `otter_list_transcripts` | List recent transcripts with summaries |
| `otter_get_transcript` | Fetch the full text of a specific transcript (with speaker labels) |
| `otter_get_user` | Get info about the authenticated Otter.ai account |

### Requirements

- Python 3.11+
- An **Otter.ai account** (email + password)

### Setup

**1. Create a virtual environment and install**

```bat
cd mcp-otter

set PY=C:\Users\%USERNAME%\AppData\Roaming\uv\python\cpython-3.14.3-windows-x86_64-none\python.exe
%PY% -m venv .venv

.venv\Scripts\activate
pip install -e .
pip install python-dotenv
```

**2. Configure credentials** — create `mcp-otter/.env`:

```env
OTTER_EMAIL=your@email.com
OTTER_PASSWORD=your-otter-password
```

**3. Smoke test**

```bat
cd mcp-otter
.venv\Scripts\python.exe run_otter.py
```

For more detail on the underlying server (available tools, example queries, how the `advanced_search` API works) see [mcp-otter/README.md](mcp-otter/README.md).

---

## Connecting to Claude Desktop

Open the config file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Both servers simultaneously

```json
{
  "mcpServers": {
    "discord": {
      "command": "C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_discord\\.venv\\Scripts\\python.exe",
      "args": ["C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_discord\\server.py"]
    },
    "todo": {
      "command": "C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_todo\\.venv\\Scripts\\python.exe",
      "args": ["C:\\delivery\\Local-Host-Discord-MCP-server\\mcp_todo\\server.py"]
    },
    "otter": {
      "command": "C:\\delivery\\Local-Host-Discord-MCP-server\\mcp-otter\\.venv\\Scripts\\python.exe",
      "args": ["C:\\delivery\\Local-Host-Discord-MCP-server\\mcp-otter\\run_otter.py"]
    }
  }
}
```

Adjust the paths if your repo is in a different location, then **restart Claude Desktop**. Both sets of tools will appear in the tool picker.

---

## Connecting to Claude Code (CLI)

```bash
claude mcp add discord \
  --command "C:/delivery/Local-Host-Discord-MCP-server/mcp_discord/.venv/Scripts/python.exe" \
  --args "C:/delivery/Local-Host-Discord-MCP-server/mcp_discord/server.py"

claude mcp add todo \
  --command "C:/delivery/Local-Host-Discord-MCP-server/mcp_todo/.venv/Scripts/python.exe" \
  --args "C:/delivery/Local-Host-Discord-MCP-server/mcp_todo/server.py"

claude mcp add otter \
  --command "C:/delivery/Local-Host-Discord-MCP-server/mcp-otter/.venv/Scripts/python.exe" \
  --args "C:/delivery/Local-Host-Discord-MCP-server/mcp-otter/run_otter.py"
```

---

## Project structure

```
Local-Host-Discord-MCP-server/
├── mcp_discord/
│   ├── server.py          # MCP server — Discord tool definitions and handlers
│   ├── discord_client.py  # discord.py wrapper with error handling
│   ├── .env               # DISCORD_TOKEN, DISCORD_GUILD_ID  (not committed)
│   └── requirements.txt
│
├── mcp_todo/
│   ├── server.py          # MCP server — To Do tool definitions and handlers
│   ├── todo_client.py     # Microsoft Graph API async wrapper
│   ├── auth.py            # MSAL device-flow + token cache management
│   ├── .env               # CLIENT_ID, CLIENT_SECRET, TENANT_ID  (not committed)
│   ├── token_cache.json   # Generated on first auth run  (not committed)
│   └── requirements.txt
│
└── mcp-otter/             # Vendored from https://github.com/DarrenZal/otter-mcp (MIT)
    ├── run_otter.py       # Local .env-loading wrapper around otter_mcp.main()
    ├── src/otter_mcp/     # Upstream server (search + transcript retrieval)
    ├── .env               # OTTER_EMAIL, OTTER_PASSWORD  (not committed)
    ├── pyproject.toml
    └── LICENSE            # MIT — Copyright (c) 2025 Darren Zal
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `DISCORD_TOKEN is not set` | Fill in `mcp_discord/.env` |
| `Missing permissions` (Discord) | Re-invite the bot with the required permissions |
| `Message Content Intent` errors | Enable the intent in the Discord Developer Portal |
| `CLIENT_ID is not set` | Fill in `mcp_todo/.env` |
| Device flow message never appears | Check that stderr is visible; Claude Desktop shows it in logs |
| `AADSTS` error during device flow | Verify the Azure app has `Tasks.ReadWrite` delegated permission and the correct redirect URI |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` inside the correct `.venv` |
| Server exits immediately | Make sure the venv `python.exe` path in the config is correct |
| `OTTER_EMAIL is not set` | Fill in `mcp-otter/.env` |
| Otter login fails | Check that the email/password work on otter.ai directly; the API is unofficial and may rate-limit |

---

## Credits

- [`mcp-otter/`](mcp-otter/) — vendored copy of [DarrenZal/otter-mcp](https://github.com/DarrenZal/otter-mcp) by Darren Zal, distributed under the MIT License. See [mcp-otter/LICENSE](mcp-otter/LICENSE).
