import asyncio
import logging

import discord

log = logging.getLogger("mcp_discord.client")


class DiscordClient:
    def __init__(self, token: str):
        self.token = token
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        self.client = discord.Client(intents=intents)
        self._ready = False
        # IMPORTANT (Python 3.14+): keep a strong reference to the gateway
        # task so it does NOT get garbage-collected mid-execution. Without
        # this, asyncio only keeps a weak reference and the connection can
        # die silently after on_ready fires - making every tool call hang.
        self._run_task: asyncio.Task | None = None

    async def start(self, connect_timeout: float = 30.0):
        """Connect to Discord and wait until ready.

        Raises discord.LoginFailure if the token is invalid.
        Raises asyncio.TimeoutError if Discord doesn't go ready in time.
        """
        ready_event = asyncio.Event()
        login_error: list[BaseException] = []

        @self.client.event
        async def on_ready():
            log.info("Discord gateway ready (user=%s)", self.client.user)
            self._ready = True
            ready_event.set()

        @self.client.event
        async def on_disconnect():
            log.warning("Discord gateway disconnected")

        @self.client.event
        async def on_resumed():
            log.info("Discord gateway resumed")

        async def _run():
            try:
                log.info("Starting Discord client...")
                await self.client.start(self.token)
            except BaseException as exc:
                log.error("Discord client exited: %r", exc)
                login_error.append(exc)
                ready_event.set()
                raise

        # Hold a strong reference on self so the task is not GC'd.
        self._run_task = asyncio.create_task(_run(), name="discord-gateway")

        try:
            await asyncio.wait_for(ready_event.wait(), timeout=connect_timeout)
        except asyncio.TimeoutError:
            log.error("Discord did not become ready within %.0fs", connect_timeout)
            self._run_task.cancel()
            raise

        if login_error:
            raise login_error[0]

    async def close(self):
        try:
            await self.client.close()
        except Exception as exc:
            log.warning("Error while closing Discord client: %r", exc)
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except (asyncio.CancelledError, Exception):
                pass

    async def send_message(self, channel_id: str, content: str) -> str:
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel is None:
                channel = await self.client.fetch_channel(int(channel_id))
            msg = await channel.send(content)
            return f"Message sent (id={msg.id})"
        except discord.Forbidden:
            return f"Error: Missing permissions to send messages in channel {channel_id}"
        except discord.NotFound:
            return f"Error: Channel {channel_id} not found"
        except discord.HTTPException as e:
            return f"Error: Discord HTTP error - {e.status} {e.text}"
        except ValueError:
            return f"Error: Invalid channel_id '{channel_id}' - must be a numeric snowflake"

    async def read_messages(self, channel_id: str, limit: int) -> list[str]:
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel is None:
                channel = await self.client.fetch_channel(int(channel_id))
            messages = []
            async for msg in channel.history(limit=max(1, min(limit, 100))):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                messages.append(f"[{ts}] {msg.author.display_name}: {msg.content}")
            return messages
        except discord.Forbidden:
            return [f"Error: Missing permissions to read messages in channel {channel_id}"]
        except discord.NotFound:
            return [f"Error: Channel {channel_id} not found"]
        except discord.HTTPException as e:
            return [f"Error: Discord HTTP error - {e.status} {e.text}"]
        except ValueError:
            return [f"Error: Invalid channel_id '{channel_id}' - must be a numeric snowflake"]

    async def list_channels(self, guild_id: str) -> list[dict]:
        try:
            guild = self.client.get_guild(int(guild_id))
            if guild is None:
                guild = await self.client.fetch_guild(int(guild_id))
            channels = []
            for ch in guild.channels:
                channels.append({
                    "id": str(ch.id),
                    "name": ch.name,
                    "type": str(ch.type),
                })
            return sorted(channels, key=lambda c: c["name"])
        except discord.Forbidden:
            return [{"error": f"Missing permissions to list channels in guild {guild_id}"}]
        except discord.NotFound:
            return [{"error": f"Guild {guild_id} not found"}]
        except discord.HTTPException as e:
            return [{"error": f"Discord HTTP error - {e.status} {e.text}"}]
        except ValueError:
            return [{"error": f"Invalid guild_id '{guild_id}' - must be a numeric snowflake"}]

    async def add_reaction(self, channel_id: str, message_id: str, emoji: str) -> str:
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel is None:
                channel = await self.client.fetch_channel(int(channel_id))
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            return f"Reaction {emoji} added to message {message_id}"
        except discord.Forbidden:
            return f"Error: Missing permissions to add reactions in channel {channel_id}"
        except discord.NotFound:
            return f"Error: Channel {channel_id} or message {message_id} not found"
        except discord.HTTPException as e:
            return f"Error: Discord HTTP error - {e.status} {e.text}"
        except ValueError:
            return f"Error: Invalid channel_id or message_id - must be numeric snowflakes"
