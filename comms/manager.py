"""
Channel Manager — starts/stops all enabled comms channels and routes messages
through Sam's ai_loop via the same queue used by the REST API.

Wire up at daemon startup:
    from comms.manager import ChannelManager
    mgr = ChannelManager(chat_input_queue)
    await mgr.start()
    # on shutdown:
    await mgr.stop()
"""

from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

from comms.channels.base import ChannelMessage

logger = logging.getLogger("sam.comms.manager")


class ChannelManager:
    def __init__(self, chat_queue: asyncio.Queue) -> None:
        """
        chat_queue: the same asyncio.Queue that api_routes.chat_input_queue uses.
        Messages pushed here are picked up by the ai_loop bridge.
        """
        self._queue = chat_queue
        self._adapters: list = []
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        """
        Load and connect all channels that are configured via environment vars.
        Channels with missing tokens are skipped gracefully.
        """
        await self._try_start_telegram()
        await self._try_start_discord()
        logger.info(f"[ChannelManager] {len(self._adapters)} channel(s) active.")

    async def stop(self) -> None:
        for adapter in self._adapters:
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.warning(f"[ChannelManager] Error disconnecting {adapter.name}: {e}")
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._adapters.clear()
        self._tasks.clear()
        logger.info("[ChannelManager] All channels stopped.")

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _message_handler(self, msg: ChannelMessage) -> str:
        """
        Receive a message from any channel, push to ai_loop queue.
        The queue item format matches api_routes.post_chat's enqueue format.
        """
        import uuid
        message_id = str(uuid.uuid4())
        await self._queue.put({
            "message_id": message_id,
            "session_id": f"{msg.channel}:{msg.from_}",
            "message": msg.text,
            # Reply callback — ai_loop response is broadcast via WS; channel adapter
            # gets the reply via the return value of the handler. For now we return ""
            # and rely on the WS broadcast reaching the dashboard. A future enhancement
            # can hook into the response pipeline to auto-reply on Telegram/Discord.
        })
        logger.info(f"[ChannelManager] [{msg.channel}] {msg.from_}: {msg.text[:60]}")
        return ""  # response will come via WS; direct reply not wired yet

    async def _try_start_telegram(self) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            logger.info("[ChannelManager] Telegram: no token set, skipping.")
            return
        try:
            from comms.channels.telegram import TelegramAdapter
            adapter = TelegramAdapter(token=token)
            adapter.on_message(self._message_handler)
            await adapter.connect()
            self._adapters.append(adapter)
            logger.info("[ChannelManager] Telegram channel connected.")
        except ImportError:
            logger.warning("[ChannelManager] Telegram: python-telegram-bot not installed. pip install python-telegram-bot")
        except Exception as e:
            logger.error(f"[ChannelManager] Telegram connect failed: {e}")

    async def _try_start_discord(self) -> None:
        token = os.getenv("DISCORD_BOT_TOKEN", "")
        if not token:
            logger.info("[ChannelManager] Discord: no token set, skipping.")
            return
        try:
            from comms.channels.discord import DiscordAdapter
            adapter = DiscordAdapter(token=token)
            adapter.on_message(self._message_handler)
            await adapter.connect()
            self._adapters.append(adapter)
            logger.info("[ChannelManager] Discord channel connected.")
        except ImportError:
            logger.warning("[ChannelManager] Discord: discord.py not installed. pip install discord.py")
        except Exception as e:
            logger.error(f"[ChannelManager] Discord connect failed: {e}")
