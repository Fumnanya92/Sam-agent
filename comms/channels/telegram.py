"""
Telegram channel adapter.
Ported from Jarvis src/comms/channels/telegram.ts

Requires: python-telegram-bot>=20  (pip install python-telegram-bot)
Config:
    TELEGRAM_BOT_TOKEN  — bot token from @BotFather
    TELEGRAM_ALLOWED_USERS — comma-separated user IDs (optional)

Usage:
    from comms.channels.telegram import TelegramAdapter
    adapter = TelegramAdapter(token="...", allowed_users=[123456])
    adapter.on_message(my_handler)
    await adapter.connect()   # blocks via Application.run_polling()
"""

from __future__ import annotations
import asyncio
import logging
import os
from typing import Optional

from comms.channels.base import ChannelMessage, MessageHandler, split_text

logger = logging.getLogger("sam.comms.telegram")


class TelegramAdapter:
    name = "telegram"

    def __init__(
        self,
        token: str = "",
        allowed_users: Optional[list[int]] = None,
    ) -> None:
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.allowed_users: list[int] = allowed_users or _parse_allowed(
            os.getenv("TELEGRAM_ALLOWED_USERS", "")
        )
        self._handler: Optional[MessageHandler] = None
        self._app = None
        self._connected = False

    def on_message(self, handler: MessageHandler) -> None:
        self._handler = handler

    def is_connected(self) -> bool:
        return self._connected

    async def send_message(self, chat_id: str | int, text: str) -> None:
        if not self._app:
            raise RuntimeError("Telegram not connected.")
        bot = self._app.bot
        for chunk in split_text(text, 4096):
            try:
                await bot.send_message(
                    chat_id=int(chat_id),
                    text=chunk,
                    parse_mode="Markdown",
                )
            except Exception:
                # Retry without markdown if parse fails
                try:
                    await bot.send_message(chat_id=int(chat_id), text=chunk)
                except Exception as e:
                    logger.error(f"[Telegram] send_message error: {e}")

    async def connect(self) -> None:
        try:
            from telegram.ext import Application, MessageHandler as TGHandler, filters
            from telegram import Update
            from telegram.ext import ContextTypes
        except ImportError:
            raise ImportError(
                "python-telegram-bot is required: pip install python-telegram-bot"
            )

        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set.")

        self._app = Application.builder().token(self.token).build()

        async def _handle(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
            msg = update.message
            if not msg or not msg.text:
                return
            user_id = msg.from_user.id if msg.from_user else 0
            if self.allowed_users and user_id not in self.allowed_users:
                logger.info(f"[Telegram] Ignoring unauthorized user {user_id}")
                return
            if not self._handler:
                return

            cm = ChannelMessage(
                id=str(msg.message_id),
                channel="telegram",
                from_=msg.from_user.username or msg.from_user.first_name if msg.from_user else "unknown",
                text=msg.text,
                timestamp=msg.date.timestamp() * 1000,
                metadata={
                    "chatId": msg.chat_id,
                    "userId": user_id,
                    "chatType": msg.chat.type,
                },
            )
            logger.info(f"[Telegram] {cm.from_}: {cm.text[:80]}")
            try:
                reply = await self._handler(cm)
                if reply:
                    await self.send_message(msg.chat_id, reply)
            except Exception as e:
                logger.error(f"[Telegram] Handler error: {e}")
                await self.send_message(msg.chat_id, "Sorry, I hit an error processing that.")

        self._app.add_handler(TGHandler(filters.TEXT & ~filters.COMMAND, _handle))
        self._connected = True
        logger.info("[Telegram] Starting polling...")
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def disconnect(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
        self._connected = False
        logger.info("[Telegram] Disconnected.")


def _parse_allowed(raw: str) -> list[int]:
    if not raw:
        return []
    try:
        return [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError:
        return []
