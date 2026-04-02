"""
FSM-хранилище на базе MongoDB для aiogram 2.x.
Состояния сохраняются между рестартами бота.
"""

import logging
from typing import Tuple

from aiogram.dispatcher.storage import BaseStorage

from bot.database.db import get_db

FSM_COLLECTION = "fsm_states"


def _make_key(chat: int, user: int) -> str:
    return f"{chat}:{user}"


class MongoStorage(BaseStorage):

    async def close(self) -> None:
        pass

    async def wait_closed(self) -> None:
        pass

    def _col(self):
        return get_db()[FSM_COLLECTION]

    def _resolve_address(self, chat=None, user=None) -> Tuple[int, int]:
        chat_id = chat or user
        user_id = user or chat
        return int(chat_id), int(user_id)

    async def _get_doc(self, chat: int, user: int) -> dict:
        key = _make_key(chat, user)
        doc = await self._col().find_one({"_id": key})
        return doc or {}

    async def _set_field(self, chat: int, user: int, field: str, value) -> None:
        key = _make_key(chat, user)
        await self._col().update_one(
            {"_id": key},
            {"$set": {field: value}},
            upsert=True,
        )

    # --- state ---

    async def get_state(self, *, chat=None, user=None, default=None):
        chat_id, user_id = self._resolve_address(chat, user)
        doc = await self._get_doc(chat_id, user_id)
        return doc.get("state", default)

    async def set_state(self, *, chat=None, user=None, state=None):
        chat_id, user_id = self._resolve_address(chat, user)
        await self._set_field(chat_id, user_id, "state", state)

    # --- data ---

    async def get_data(self, *, chat=None, user=None, default=None):
        chat_id, user_id = self._resolve_address(chat, user)
        doc = await self._get_doc(chat_id, user_id)
        return doc.get("data", default or {})

    async def set_data(self, *, chat=None, user=None, data=None):
        chat_id, user_id = self._resolve_address(chat, user)
        await self._set_field(chat_id, user_id, "data", data)

    async def update_data(self, *, chat=None, user=None, data=None, **kwargs):
        chat_id, user_id = self._resolve_address(chat, user)
        current = await self.get_data(chat=chat_id, user=user_id)
        if data:
            current.update(data)
        current.update(kwargs)
        await self.set_data(chat=chat_id, user=user_id, data=current)
        return current

    # --- bucket (aiogram 2.x requirement) ---

    async def get_bucket(self, *, chat=None, user=None, default=None):
        chat_id, user_id = self._resolve_address(chat, user)
        doc = await self._get_doc(chat_id, user_id)
        return doc.get("bucket", default or {})

    async def set_bucket(self, *, chat=None, user=None, bucket=None):
        chat_id, user_id = self._resolve_address(chat, user)
        await self._set_field(chat_id, user_id, "bucket", bucket)

    async def update_bucket(self, *, chat=None, user=None, bucket=None, **kwargs):
        chat_id, user_id = self._resolve_address(chat, user)
        current = await self.get_bucket(chat=chat_id, user=user_id)
        if bucket:
            current.update(bucket)
        current.update(kwargs)
        await self.set_bucket(chat=chat_id, user=user_id, bucket=current)
        return current

    async def reset_state(self, *, chat=None, user=None, with_data=True):
        chat_id, user_id = self._resolve_address(chat, user)
        key = _make_key(chat_id, user_id)
        if with_data:
            await self._col().delete_one({"_id": key})
        else:
            await self._set_field(chat_id, user_id, "state", None)

    async def finish(self, *, chat=None, user=None):
        await self.reset_state(chat=chat, user=user, with_data=True)
