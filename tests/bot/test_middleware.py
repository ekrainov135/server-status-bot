"""Tests for `app.bot.middleware.AdminAccessMiddleware`.

`AdminAccessMiddleware` is registered as an *outer* middleware on
`dp.update` (see `run.py`/`app/bot/controller.py`), which means the `event`
argument aiogram actually passes at runtime is an `aiogram.types.Update`,
never a bare `Message` or `CallbackQuery` -- confirmed by reading
`Dispatcher.feed_update`, which calls
`self.update.wrap_outer_middleware(self.update.trigger, update, ...)`.
All fakes below model `event` accordingly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.middleware import AdminAccessMiddleware

ADMIN_ID = 111
STRANGER_ID = 999


def make_update(*, message=None, callback_query=None):
    """Builds an Update-like double exposing only `.message`/`.callback_query`,
    matching what `AdminAccessMiddleware.__call__` actually reads.
    """
    update = MagicMock()
    update.message = message
    update.callback_query = callback_query
    return update


def make_message(user_id: int):
    message = MagicMock()
    message.from_user.id = user_id
    message.bot = AsyncMock()
    message.answer = AsyncMock()
    return message


def make_callback_query(user_id: int):
    callback_query = MagicMock()
    callback_query.from_user.id = user_id
    callback_query.bot = AsyncMock()
    return callback_query


@pytest.fixture
def middleware():
    return AdminAccessMiddleware(allowed_users=[ADMIN_ID])


class TestAdminAccessBlocksStrangers:
    async def test_stranger_message_does_not_reach_the_handler(self, middleware):
        message = make_message(STRANGER_ID)
        update = make_update(message=message)
        handler = AsyncMock()

        await middleware(handler, update, {})

        handler.assert_not_awaited()

    async def test_stranger_callback_query_does_not_reach_the_handler(self, middleware):
        callback_query = make_callback_query(STRANGER_ID)
        update = make_update(callback_query=callback_query)
        handler = AsyncMock()

        await middleware(handler, update, {})

        handler.assert_not_awaited()


class TestAdminAccessIgnoresOtherUpdateTypes:
    async def test_update_without_message_or_callback_query_is_ignored(self, middleware):
        update = make_update(message=None, callback_query=None)
        handler = AsyncMock()

        result = await middleware(handler, update, {})

        handler.assert_not_awaited()
        assert result is None
