"""Wrapper: loads .env then runs otter-mcp main().

This keeps credentials out of claude_desktop_config.json and matches the
.env pattern used by mcp_discord and mcp_todo.
"""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from otter_mcp import main

if __name__ == "__main__":
    main()
