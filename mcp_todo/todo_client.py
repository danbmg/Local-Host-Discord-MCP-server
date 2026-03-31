"""
Async Microsoft Graph API wrapper for Microsoft To Do.

Endpoints used:
  GET  /me/todo/lists
  GET  /me/todo/lists/{listId}/tasks
  POST /me/todo/lists/{listId}/tasks
  PATCH /me/todo/lists/{listId}/tasks/{taskId}
"""
import asyncio
from typing import Callable

import httpx

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class TodoClient:
    def __init__(self, token_getter: Callable[[], str]):
        """
        token_getter: a zero-argument sync callable that returns an access token.
        It is called in a thread executor so blocking I/O (MSAL refresh) is safe.
        """
        self._get_token = token_getter
        self._token: str = ""
        self._client: httpx.AsyncClient | None = None

    async def start(self):
        """Authenticate and create the persistent HTTP client."""
        self._token = await self._run_sync(self._get_token)
        self._client = httpx.AsyncClient(base_url=GRAPH_BASE, timeout=30.0)

    async def close(self):
        if self._client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_sync(fn: Callable, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def _refresh_token(self):
        self._token = await self._run_sync(self._get_token)

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        """Execute a Graph API request, retrying once after a 401 (token refresh)."""
        assert self._client is not None, "TodoClient not started"

        for attempt in range(2):
            resp = await self._client.request(
                method, path, headers=self._auth_header(), **kwargs
            )
            if resp.status_code == 401 and attempt == 0:
                await self._refresh_token()
                continue
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error_body = ""
                try:
                    error_body = exc.response.json().get("error", {}).get("message", "")
                except Exception:
                    pass
                raise httpx.HTTPStatusError(
                    error_body or str(exc), request=exc.request, response=exc.response
                ) from exc
            return resp.json() if resp.content else {}

        raise RuntimeError("Request failed after token refresh")

    # ------------------------------------------------------------------
    # To Do API methods
    # ------------------------------------------------------------------

    async def get_task_lists(self) -> list[dict]:
        try:
            data = await self._request("GET", "/me/todo/lists")
            return [
                {"id": lst["id"], "name": lst["displayName"]}
                for lst in data.get("value", [])
            ]
        except httpx.HTTPStatusError as e:
            return [{"error": f"Graph API error: {e}"}]
        except Exception as e:
            return [{"error": f"Unexpected error: {e}"}]

    async def get_tasks(self, list_id: str) -> list[dict]:
        try:
            data = await self._request("GET", f"/me/todo/lists/{list_id}/tasks")
            tasks = []
            for t in data.get("value", []):
                due = None
                if t.get("dueDateTime"):
                    due = t["dueDateTime"].get("dateTime", "")[:10]
                tasks.append({
                    "id": t["id"],
                    "title": t.get("title", ""),
                    "status": t.get("status", ""),
                    "due_date": due,
                    "importance": t.get("importance", ""),
                })
            return tasks
        except httpx.HTTPStatusError as e:
            return [{"error": f"Graph API error: {e}"}]
        except Exception as e:
            return [{"error": f"Unexpected error: {e}"}]

    async def create_task(
        self, list_id: str, title: str, due_date: str | None = None
    ) -> str:
        body: dict = {"title": title}
        if due_date:
            # Accepts "YYYY-MM-DD"; Graph expects ISO 8601 datetime + timezone
            body["dueDateTime"] = {
                "dateTime": f"{due_date}T00:00:00",
                "timeZone": "UTC",
            }
        try:
            result = await self._request(
                "POST", f"/me/todo/lists/{list_id}/tasks", json=body
            )
            return f"Task created (id={result.get('id', '?')}): {result.get('title', title)}"
        except httpx.HTTPStatusError as e:
            return f"Error creating task: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    async def complete_task(self, list_id: str, task_id: str) -> str:
        try:
            await self._request(
                "PATCH",
                f"/me/todo/lists/{list_id}/tasks/{task_id}",
                json={"status": "completed"},
            )
            return f"Task {task_id} marked as completed"
        except httpx.HTTPStatusError as e:
            return f"Error completing task: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"
