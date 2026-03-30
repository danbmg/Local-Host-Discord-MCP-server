import discord
from typing import Optional


class DiscordClient:
    def __init__(self, token: str):
        self.token = token
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        self.client = discord.Client(intents=intents)
        self._ready = False

    async def start(self):
        """Connect to Discord and wait until ready."""
        import asyncio

        ready_event = asyncio.Event()

        @self.client.event
        async def on_ready():
            self._ready = True
            ready_event.set()

        asyncio.create_task(self.client.start(self.token))
        await ready_event.wait()

    async def close(self):
        await self.client.close()

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
            return f"Error: Discord HTTP error — {e.status} {e.text}"
        except ValueError:
            return f"Error: Invalid channel_id '{channel_id}' — must be a numeric snowflake"

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
            return [f"Error: Discord HTTP error — {e.status} {e.text}"]
        except ValueError:
            return [f"Error: Invalid channel_id '{channel_id}' — must be a numeric snowflake"]

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
            return [{"error": f"Discord HTTP error — {e.status} {e.text}"}]
        except ValueError:
            return [{"error": f"Invalid guild_id '{guild_id}' — must be a numeric snowflake"}]

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
        except discord.InvalidArgument:
            return f"Error: Invalid emoji '{emoji}'"
        except discord.HTTPException as e:
            return f"Error: Discord HTTP error — {e.status} {e.text}"
        except ValueError:
            return f"Error: Invalid channel_id or message_id — must be numeric snowflakes"
