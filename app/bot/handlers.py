# mypy: disable-error-code=union-attr

import contextlib
from typing import Any

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from lib.aiogram_keyboard.helpers import KeyboardSession
from lib.aiogram_keyboard.models import KeyboardCD

from ..system import SystemManager
from .app_registry import AppRegistry


async def cmd_start(message: Message, state: FSMContext, app: AppRegistry) -> None:
    """Handle /start: reset navigation to the main screen.

    Deletes the previous keyboard message if one exists (best-effort;
    Telegram may reject deleting old messages) and sends a fresh one,
    carrying over the previously selected language.
    """

    async with KeyboardSession(state, key='kb_ctx') as ctx:
        if 'breadcrumbs' in ctx.dialog.data:
            with contextlib.suppress(TelegramBadRequest, ValueError):
                await message.bot.delete_message(
                    chat_id=message.chat.id, message_id=ctx.dialog.data['message_id']
                )

        save_data: dict[str, Any] = {'breadcrumbs': ['main']}
        if 'lang' in ctx.dialog.data:
            save_data['lang'] = ctx.dialog.data['lang']
        ctx.dialog.data = save_data

        frame = await app.render(ctx)
        sent = await message.answer(frame.text, reply_markup=frame.markup)

        ctx.dialog.data['message_id'] = sent.message_id


async def handle_kb(
    query: CallbackQuery,
    callback_data: KeyboardCD,
    state: FSMContext,
    app: AppRegistry,
    system: SystemManager,
) -> None:
    """Handle an inline keyboard button press.

    Ignores callbacks from a stale keyboard message (e.g. after a
    restart) by deleting it instead of dispatching. Otherwise
    dispatches the action, re-renders the screen, and edits the
    message only if the text or markup actually changed.
    """

    async with KeyboardSession(state, key='kb_ctx') as ctx:
        is_message_active = ctx.dialog.data.get(
            'breadcrumbs'
        ) and query.message.message_id == ctx.dialog.data.get('message_id')

        if not is_message_active:
            with contextlib.suppress(TelegramBadRequest, ValueError):
                await query.bot.delete_message(
                    chat_id=query.message.chat.id, message_id=query.message.message_id
                )
            return

        dispatch_result = await app.dispatch(callback_data, ctx, system=system)

        frame = await app.render(ctx)
        show_alert = ctx.dialog.data.pop('show_alert', False)

        if show_alert:
            await query.answer(dispatch_result or frame.text, show_alert=True)

        old_markup = query.message.reply_markup.model_dump() if query.message.reply_markup else None
        is_updated = frame.text != query.message.text or old_markup != frame.markup.model_dump()

        if is_updated:
            await query.bot.edit_message_text(
                text=frame.text,
                reply_markup=frame.markup,
                chat_id=query.message.chat.id,
                message_id=ctx.dialog.data['message_id'],
            )
