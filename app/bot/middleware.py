from collections.abc import Callable
from typing import Any

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject, Update


class AdminAccessMiddleware(BaseMiddleware):
    def __init__(self, allowed_users: list | set):
        super().__init__()
        self.allowed_users = set(allowed_users)

    async def __call__(self, handler: Callable, event: TelegramObject, data: dict[str, Any]):
        if not isinstance(event, Update):
            return

        if event.message is not None and event.message.from_user is not None:
            user_id = event.message.from_user.id
        elif event.callback_query is not None and event.callback_query.from_user is not None:
            user_id = event.callback_query.from_user.id
        else:
            return

        if user_id not in self.allowed_users:
            return

        return await handler(event, data)
