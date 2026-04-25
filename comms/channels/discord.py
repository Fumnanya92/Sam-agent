"""
Discord channel adapter.
Ported from Jarvis src/comms/channels/discord.ts

Requires: discord.py>=2  (pip install discord.py)
Config:
    DISCORD_BOT_TOKEN   — bot token from Discord developer portal
    DISCORD_ALLOWED_USERS — comma-separated user IDs (optional)
    DISCORD_GUILD_ID      — restrict to one server (optional)

Usage:
    from comms.channels.discord import DiscordAdapter
    adapter = DiscordAdapter(token="...", allowed_users=["123456"])
    adapter.on_message(my_handler)
    await adapter.connect()
"""

from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

from comms.channels.base import ChannelMessage, MessageHandler, split_text

logger = logging.getLogger("sam.comms.discord")


class DiscordAdapter:
    name = "discord"

    def __init__(
        self,
        token: str = "",
        allowed_users: Optional[list[str]] = None,
        guild_id: Optional[str] = None,
    ) -> None:
        self.token = token or os.getenv("DISCORD_BOT_TOKEN", "")
        self.allowed_users: list[str] = allowed_users or _parse_list(
            os.getenv("DISCORD_ALLOWED_USERS", "")
        )
        self.guild_id = guild_id or os.getenv("DISCORD_GUILD_ID", "")
        self._handler: Optional[MessageHandler] = None
        self._client = None
        self._connected = False
        self._ready_event: asyncio.Event = asyncio.Event()

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def is_connected(self) -> bool:
        return self._connected

    async def send_message(self, channel_id: str | int, text: str) -> None:
        if not self._client:
            raise RuntimeError("Discord not connected.")
        try:
            import discord
            channel = await self._client.fetch_channel(int(channel_id))
            if not channel or not hasattr(channel, "send"):
                raise ValueError(f"Not a text channel: {channel_id}")
            for chunk in split_text(text, 2000):
                await channel.send(chunk)
        except Exception as e:
            logger.error(f"[Discord] send_message error: {e}")

    async def connect(self) -> None:
        try:
            import discord
        except ImportError:
            raise ImportError("discord.py is required: pip install discord.py")

        if not self.token:
            raise ValueError("DISCORD_BOT_TOKEN is not set.")

        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        self._client = discord.Client(intents=intents)
        client = self._client

        @client.event
        async def on_ready():
            self._connected = True
            logger.info(f"[Discord] Connected as {client.user}")
            self._ready_event.set()

        @client.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return
            if not self._handler:
                return
            if self.allowed_users and str(message.author.id) not in self.allowed_users:
                return
            if self.guild_id and message.guild and str(message.guild.id) != self.guild_id:
                return

            text = message.content
            if not text:
                return

            cm = ChannelMessage(
                id=str(message.id),
                channel="discord",
                from_=message.author.name,
                text=text,
                timestamp=message.created_at.timestamp() * 1000,
                metadata={
                    "userId": str(message.author.id),
                    "channelId": str(message.channel.id),
                    "guildId": str(message.guild.id) if message.guild else None,
                    "isDM": message.guild is None,
                },
            )
            logger.info(f"[Discord] {cm.from_}: {cm.text[:80]}")
            try:
                if hasattr(message.channel, "typing"):
                    async with message.channel.typing():
                        reply = await self._handler(cm)
                else:
                    reply = await self._handler(cm)
                if reply:
                    for chunk in split_text(reply, 2000):
                        await message.reply(chunk)
            except Exception as e:
                logger.error(f"[Discord] Handler error: {e}")
                try:
                    await message.reply("Sorry, I hit an error processing that.")
                except Exception:
                    pass

        # Start client in background task — don't block
        asyncio.create_task(client.start(self.token))
        await asyncio.wait_for(self._ready_event.wait(), timeout=30)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
        self._connected = False
        logger.info("[Discord] Disconnected.")


def _parse_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]
