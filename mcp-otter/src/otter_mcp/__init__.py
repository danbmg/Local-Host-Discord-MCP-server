"""
Otter.ai MCP Server
Provides transcript search and retrieval via MCP protocol
"""

from .server import mcp, main
from .client import OtterAI, OtterAIException

__version__ = "0.1.0"
__all__ = ["mcp", "main", "OtterAI", "OtterAIException"]
