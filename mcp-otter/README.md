# Otter MCP

MCP (Model Context Protocol) server for [Otter.ai](https://otter.ai) transcript search and retrieval.

Enables AI assistants like Claude to search and retrieve meeting transcripts from your Otter.ai account.

## Features

- **Full-text search** across all transcripts (not just titles/summaries)
- **Speaker identification** in search results
- **Context snippets** showing where matches occur
- **Full transcript retrieval** with speaker labels
- **Recent transcripts listing** with summaries

## Installation

### Using pip

```bash
pip install otter-mcp
```

### From source

```bash
git clone https://github.com/DarrenZal/otter-mcp.git
cd otter-mcp
pip install -e .
```

## Configuration

### Claude Code

Add to your MCP servers using the CLI:

```bash
claude mcp add otter -e OTTER_EMAIL=your@email.com -e OTTER_PASSWORD=yourpassword -- otter-mcp
```

Or manually add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "otter": {
      "command": "otter-mcp",
      "env": {
        "OTTER_EMAIL": "your@email.com",
        "OTTER_PASSWORD": "yourpassword"
      }
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "otter": {
      "command": "otter-mcp",
      "env": {
        "OTTER_EMAIL": "your@email.com",
        "OTTER_PASSWORD": "yourpassword"
      }
    }
  }
}
```

## Available Tools

### `otter_search`

Search across all transcripts by keyword, name, or phrase.

```
otter_search(query="project meeting", limit=10)
```

Returns matching transcripts with:
- Title and ID
- Date and duration
- Speaker names
- Context snippets showing matches

### `otter_list_transcripts`

List recent transcripts with summaries.

```
otter_list_transcripts(limit=20)
```

### `otter_get_transcript`

Get the full text of a specific transcript.

```
otter_get_transcript(transcript_id="abc123...")
```

### `otter_get_user`

Get information about the authenticated Otter.ai account.

```
otter_get_user()
```

## Examples

**Find all meetings with a specific person:**
```
otter_search("John Smith")
```

**Search for a topic discussed:**
```
otter_search("budget proposal Q4")
```

**Get full transcript for follow-up:**
```
otter_get_transcript("SwpVmqfaM86nEiqEfTnFm79X5LY")
```

## How It Works

This MCP server uses the unofficial Otter.ai API to:

1. Authenticate with your Otter.ai credentials
2. Use the `advanced_search` endpoint for full-text search across all transcripts
3. Retrieve full transcript content with speaker diarization

The `advanced_search` API searches the actual transcript content, not just titles and summaries, making it much more useful for finding specific conversations.

## Security Notes

- Credentials are passed via environment variables, not stored in code
- Uses HTTPS for all API communication
- Session tokens are managed in memory only

## Credits

API client based on [gmchad/otterai-api](https://github.com/gmchad/otterai-api) with additions for advanced search functionality.

## License

MIT License - see [LICENSE](LICENSE) for details.
