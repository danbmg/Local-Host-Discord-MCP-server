"""
Otter.ai MCP Server

Provides transcript search and retrieval via Model Context Protocol (MCP).
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .client import OtterAI, OtterAIException

# Initialize FastMCP server
mcp = FastMCP("otter-mcp")

# Global otter client (initialized on first use)
_otter_client = None


def get_otter_client() -> OtterAI:
    """Get or create authenticated Otter client"""
    global _otter_client
    if _otter_client is None:
        email = os.environ.get("OTTER_EMAIL")
        password = os.environ.get("OTTER_PASSWORD")
        if not email or not password:
            raise OtterAIException(
                "OTTER_EMAIL and OTTER_PASSWORD environment variables required. "
                "Set these in your MCP server configuration."
            )
        _otter_client = OtterAI()
        result = _otter_client.login(email, password)
        if result.get('status') != 200:
            raise OtterAIException(f"Login failed: {result}")
    return _otter_client


def format_timestamp(ts: int) -> str:
    """Convert Unix timestamp to readable date with relative formatting"""
    if not ts:
        return "Unknown date"
    try:
        dt = datetime.fromtimestamp(ts)
        today = datetime.now().date()
        ts_date = dt.date()

        if ts_date == today:
            return f"Today at {dt.strftime('%I:%M %p')}"
        elif ts_date == today - timedelta(days=1):
            return f"Yesterday at {dt.strftime('%I:%M %p')}"
        elif ts_date >= today - timedelta(days=7):
            return f"{dt.strftime('%A')} at {dt.strftime('%I:%M %p')}"  # Day name for last week
        else:
            return dt.strftime("%Y-%m-%d %I:%M %p")
    except:
        return "Unknown date"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable"""
    if not seconds:
        return "Unknown duration"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes >= 60:
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours}h {minutes}m"
    return f"{minutes}m {secs}s"


def parse_date_filter(date_filter: str) -> tuple[Optional[int], Optional[int]]:
    """
    Parse date filter string into (start_timestamp, end_timestamp)

    Supports:
    - "today"
    - "yesterday"
    - "this week" / "this_week"
    - "last week" / "last_week"
    - "YYYY-MM-DD" (specific date)
    - "YYYY-MM-DD to YYYY-MM-DD" (date range)
    """
    if not date_filter:
        return None, None

    date_filter = date_filter.lower().strip()
    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day)

    if date_filter == "today":
        start = today_start
        end = today_start + timedelta(days=1)
    elif date_filter == "yesterday":
        start = today_start - timedelta(days=1)
        end = today_start
    elif date_filter in ("this week", "this_week"):
        # Start of this week (Monday)
        start = today_start - timedelta(days=today_start.weekday())
        end = now
    elif date_filter in ("last week", "last_week"):
        # Last week Monday to Sunday
        this_week_start = today_start - timedelta(days=today_start.weekday())
        start = this_week_start - timedelta(days=7)
        end = this_week_start
    elif " to " in date_filter:
        # Date range: "2025-01-15 to 2025-01-20"
        parts = date_filter.split(" to ")
        try:
            start = datetime.strptime(parts[0].strip(), "%Y-%m-%d")
            end = datetime.strptime(parts[1].strip(), "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            return None, None
    else:
        # Single date: "2025-01-20"
        try:
            start = datetime.strptime(date_filter, "%Y-%m-%d")
            end = start + timedelta(days=1)
        except ValueError:
            return None, None

    return int(start.timestamp()), int(end.timestamp())


@mcp.tool()
def otter_search(query: str, limit: int = 10, date_filter: str = "") -> str:
    """
    Search across all Otter.ai transcripts by keyword.

    Performs full-text search across transcript content, not just titles.
    Returns matching transcripts with speaker names, dates, and relevant snippets.

    Args:
        query: Search query - keywords, names, or phrases to find
        limit: Maximum number of results to return (default: 10)
        date_filter: Optional date filter. Supports:
            - "today" - meetings from today
            - "yesterday" - meetings from yesterday
            - "this week" - meetings from this week
            - "last week" - meetings from last week
            - "2025-01-20" - meetings from specific date
            - "2025-01-15 to 2025-01-20" - meetings in date range

    Returns:
        Formatted list of matching transcripts with dates and context snippets
    """
    try:
        otter = get_otter_client()
        result = otter.search(query, size=limit * 2)  # Get extra to filter by date
        hits = result.get('hits', [])

        # Parse date filter
        start_ts, end_ts = parse_date_filter(date_filter)

        results = []
        for hit in hits:
            start_time = hit.get("start_time", 0)

            # Apply date filter if specified
            if start_ts and end_ts:
                if not (start_ts <= start_time < end_ts):
                    continue

            # Get matched transcript snippets
            matched_snippets = []
            for mt in hit.get('matched_transcripts', [])[:3]:
                snippet = mt.get('matched_transcript', '')
                speaker = mt.get('speaker_name', 'Unknown')
                if len(snippet) > 150:
                    snippet = snippet[:150] + "..."
                matched_snippets.append(f"    [{speaker}]: \"{snippet}\"")

            results.append({
                "id": hit.get("speech_otid"),
                "title": hit.get("title") or "Untitled",
                "speakers": hit.get("speaker", []),
                "duration": format_duration(hit.get("duration", 0)),
                "date": format_timestamp(start_time),
                "date_ts": start_time,
                "matched_snippets": matched_snippets
            })

            if len(results) >= limit:
                break

        if not results:
            filter_msg = f" with date filter '{date_filter}'" if date_filter else ""
            return f"No transcripts found matching '{query}'{filter_msg}"

        # Sort by date (most recent first)
        results.sort(key=lambda x: x["date_ts"], reverse=True)

        output = f"Found {len(results)} transcripts matching '{query}'"
        if date_filter:
            output += f" (filtered by: {date_filter})"
        output += ":\n\n"

        for r in results:
            output += f"**{r['title']}**\n"
            output += f"  Date: {r['date']}\n"
            output += f"  ID: {r['id']}\n"
            output += f"  Duration: {r['duration']}\n"
            if r['speakers']:
                output += f"  Speakers: {', '.join(r['speakers'])}\n"
            if r['matched_snippets']:
                output += f"  Matches:\n"
                for snippet in r['matched_snippets']:
                    output += f"{snippet}\n"
            output += "\n"

        return output

    except OtterAIException as e:
        return f"Otter API error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def otter_list_transcripts(limit: int = 20, date_filter: str = "") -> str:
    """
    List recent Otter.ai transcripts with titles, dates, and summaries.

    Args:
        limit: Maximum number of transcripts to return (default: 20)
        date_filter: Optional date filter. Supports:
            - "today" - meetings from today
            - "yesterday" - meetings from yesterday
            - "this week" - meetings from this week
            - "last week" - meetings from last week
            - "2025-01-20" - meetings from specific date
            - "2025-01-15 to 2025-01-20" - meetings in date range

    Returns:
        Formatted list of recent transcripts with dates
    """
    try:
        otter = get_otter_client()
        response = otter.get_speeches(page_size=limit * 2)  # Get extra to filter
        speeches = response.get("data", {}).get("speeches", [])

        # Parse date filter
        start_ts, end_ts = parse_date_filter(date_filter)

        results = []
        for speech in speeches:
            created = speech.get("created_at", 0)

            # Apply date filter if specified
            if start_ts and end_ts:
                if not (start_ts <= created < end_ts):
                    continue

            summary = speech.get("summary") or "No summary"
            if len(summary) > 150:
                summary = summary[:150] + "..."

            results.append({
                "id": speech.get("otid"),
                "title": speech.get("title") or "Untitled",
                "summary": summary,
                "date": format_timestamp(created),
                "date_ts": created,
                "duration": format_duration(speech.get("duration", 0))
            })

            if len(results) >= limit:
                break

        if not results:
            filter_msg = f" with date filter '{date_filter}'" if date_filter else ""
            return f"No transcripts found{filter_msg}"

        output = f"Found {len(results)} transcripts"
        if date_filter:
            output += f" (filtered by: {date_filter})"
        output += ":\n\n"

        for r in results:
            output += f"**{r['title']}**\n"
            output += f"  Date: {r['date']}\n"
            output += f"  ID: {r['id']}\n"
            output += f"  Duration: {r['duration']}\n"
            output += f"  Summary: {r['summary']}\n\n"

        return output

    except OtterAIException as e:
        return f"Otter API error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def otter_get_transcript(transcript_id: str) -> str:
    """
    Get the full transcript text for a specific Otter recording.

    Args:
        transcript_id: The Otter transcript ID (otid) - can be found via search or list

    Returns:
        Full transcript text with speaker labels
    """
    try:
        otter = get_otter_client()
        speech = otter.get_speech(transcript_id)

        speech_data = speech.get("data", {}).get("speech", {})
        title = speech_data.get("title", "Untitled")
        created = speech_data.get("created_at", 0)
        duration = speech_data.get("duration", 0)
        transcripts = speech_data.get("transcripts", [])

        header = f"# {title}\n\n"
        header += f"**Date:** {format_timestamp(created)}\n"
        header += f"**Duration:** {format_duration(duration)}\n\n"
        header += "---\n\n"

        if not transcripts:
            return header + "No transcript content found."

        full_text = [header]
        for t in transcripts:
            speaker = t.get("speaker_name", "Speaker")
            text = t.get("transcript", "")
            if text:
                full_text.append(f"**{speaker}:** {text}")

        return "\n\n".join(full_text)

    except OtterAIException as e:
        return f"Otter API error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


@mcp.tool()
def otter_get_user() -> str:
    """
    Get information about the authenticated Otter.ai user account.

    Returns:
        User account details including email and subscription info
    """
    try:
        otter = get_otter_client()
        user = otter.get_user()
        return json.dumps(user.get('data', user), indent=2)

    except OtterAIException as e:
        return f"Otter API error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def main():
    """Entry point for the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
