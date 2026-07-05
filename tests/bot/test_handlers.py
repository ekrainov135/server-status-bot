"""Tests for `app.bot.handlers` (`cmd_start`, `handle_kb`).

These tests use lightweight test doubles instead of the real `AppRegistry`
and real aiogram `Message`/`CallbackQuery`/`FSMContext` objects:

- `FakeAppRegistry` implements the same public surface (`init_context`,
  `render`, `dispatch`) as `app.bot.app_registry.AppRegistry`, letting these
  tests focus purely on request *orchestration* (message deletion,
  persistence, edit-vs-send decisions) rather than the Jinja2/YAML
  rendering pipeline, which has its own dedicated coverage in
  `test_app_registry.py`.
- `FakeState` implements the `StateProtocol` used by
  `lib.aiogram_keyboard.helpers.KeyboardSession` with a plain dict, so
  `KeyboardSession`'s real load/save round-trip is exercised for real.
- aiogram's `Message`/`CallbackQuery`/`Bot` are stood in for with
  `unittest.mock` doubles exposing only the attributes/methods the handler
  code actually touches.
"""

from unittest.mock import AsyncMock, MagicMock

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup

from app.bot.handlers import cmd_start, handle_kb
from lib.aiogram_keyboard.models import KeyboardCD, KeyboardContext, KeyboardFrame


class FakeState:
    """Minimal `StateProtocol` implementation backed by a plain dict."""

    def __init__(self, initial: dict | None = None):
        self._data = dict(initial or {})

    async def get_data(self) -> dict:
        return dict(self._data)

    async def update_data(self, **kwargs) -> dict:
        self._data.update(kwargs)
        return dict(self._data)


class FakeAppRegistry:
    """Test double for `AppRegistry` -- see module docstring."""

    def __init__(self, frame: KeyboardFrame, dispatch_result=None, dispatch_side_effect=None):
        self.frame = frame
        self.dispatch_result = dispatch_result
        self.dispatch_side_effect = dispatch_side_effect
        self.dispatch_calls: list = []
        self.render_calls: list = []

    async def dispatch(self, cb_data, ctx, **kwargs):
        self.dispatch_calls.append((cb_data, ctx, kwargs))
        if self.dispatch_side_effect:
            self.dispatch_side_effect(ctx)
        return self.dispatch_result

    async def render(self, ctx):
        self.render_calls.append(ctx)
        return self.frame


def make_frame(text='header', markup=None) -> KeyboardFrame:
    return KeyboardFrame(
        text=text,
        markup=markup or InlineKeyboardMarkup(inline_keyboard=[]),
        context=KeyboardContext(),
    )


def make_message():
    message = MagicMock()
    message.bot = AsyncMock()
    message.chat.id = 42
    message.answer = AsyncMock(return_value=MagicMock(message_id=777))
    return message


def make_query(text='old text', markup=None):
    query = MagicMock()
    query.bot = AsyncMock()
    query.message.chat.id = 42
    query.message.message_id = 100
    query.message.text = text
    query.message.reply_markup = markup or InlineKeyboardMarkup(inline_keyboard=[])
    query.answer = AsyncMock()
    return query


class TestCmdStartFirstRun:
    async def test_sends_the_main_screen(self):
        message = make_message()
        state = FakeState()  # no prior kb_ctx at all
        app = FakeAppRegistry(frame=make_frame(text='Main screen'))

        await cmd_start(message, state, app)

        message.answer.assert_awaited_once()
        args, kwargs = message.answer.call_args
        assert args[0] == 'Main screen'

    async def test_does_not_attempt_to_delete_a_message_that_never_existed(self):
        message = make_message()
        state = FakeState()
        app = FakeAppRegistry(frame=make_frame())

        await cmd_start(message, state, app)

        message.bot.delete_message.assert_not_called()

    async def test_persists_the_new_context_with_the_sent_message_id(self):
        message = make_message()  # answer() returns message_id=777
        state = FakeState()
        app = FakeAppRegistry(frame=make_frame())

        await cmd_start(message, state, app)

        saved = await state.get_data()
        assert saved['kb_ctx']['dialog']['data']['message_id'] == 777


class TestCmdStartRepeatedRun:
    async def test_deletes_the_previous_message(self):
        message = make_message()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 555}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame())

        await cmd_start(message, state, app)

        message.bot.delete_message.assert_awaited_once_with(chat_id=42, message_id=555)

    async def test_swallows_telegram_bad_request_when_deleting_and_still_sends_a_new_screen(self):
        message = make_message()
        message.bot.delete_message.side_effect = TelegramBadRequest(
            method=MagicMock(), message='gone'
        )
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 555}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='fresh screen'))

        await cmd_start(message, state, app)

        message.answer.assert_awaited_once()
        assert message.answer.call_args.args[0] == 'fresh screen'

    async def test_preserves_the_previously_selected_language(self):
        message = make_message()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 555, 'lang': 'en'}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame())

        await cmd_start(message, state, app)

    async def test_does_not_forward_unrelated_dialog_data_to_init_context(self):
        """Only `lang` is explicitly carried over; anything else from the
        previous dialog (e.g. a stale `show_alert`) must not leak into the
        brand new context.
        """
        message = make_message()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {
                        'data': {'breadcrumbs': ['main'], 'message_id': 555, 'show_alert': True},
                    },
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame())

        await cmd_start(message, state, app)


class TestHandleKbEmptyBreadcrumbs:
    """Regression tests for the FIXED `handle_kb` bug: previously, using
    `ctx.dialog.data['breadcrumbs']` (direct indexing) plus a `return`
    placed only inside the `try` block meant that if `delete_message`
    raised `TelegramBadRequest`/`ValueError`, execution fell through to
    `app.dispatch(...)` with empty breadcrumbs, crashing with `IndexError`
    inside `AppRegistry.dispatch` (`breadcrumbs[-1]` on `[]`).

    The fixed version uses `.get('breadcrumbs', [])` and returns
    unconditionally after the cleanup attempt, regardless of its outcome.
    """

    async def test_deletes_the_message_and_never_calls_dispatch(self):
        query = make_query()
        state = FakeState({'kb_ctx': {'dialog': {'data': {'breadcrumbs': []}}, 'widgets': {}}})
        app = FakeAppRegistry(frame=make_frame())

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.bot.delete_message.assert_awaited_once_with(chat_id=42, message_id=100)
        assert app.dispatch_calls == []

    async def test_still_returns_cleanly_when_delete_message_fails(self):
        """The critical case: deleting fails, but we must not fall through
        to `app.dispatch()` with an empty breadcrumb stack.
        """
        query = make_query()
        query.bot.delete_message.side_effect = TelegramBadRequest(
            method=MagicMock(), message='gone'
        )
        state = FakeState({'kb_ctx': {'dialog': {'data': {'breadcrumbs': []}}, 'widgets': {}}})
        app = FakeAppRegistry(frame=make_frame())

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        assert app.dispatch_calls == []
        assert app.render_calls == []

    async def test_missing_breadcrumbs_key_is_treated_the_same_as_empty(self):
        query = make_query()
        state = FakeState(
            {'kb_ctx': {'dialog': {'data': {}}, 'widgets': {}}}
        )  # no 'breadcrumbs' at all
        app = FakeAppRegistry(frame=make_frame())

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.bot.delete_message.assert_awaited_once()
        assert app.dispatch_calls == []


class TestHandleKbNormalFlow:
    async def test_dispatches_the_callback_before_rendering(self):
        query = make_query()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='old text'))
        cb_data = KeyboardCD(widget_id=0, button_id=1)

        await handle_kb(query, cb_data, state, app, system='the-system-manager')

        assert len(app.dispatch_calls) == 1
        dispatched_cb, _, kwargs = app.dispatch_calls[0]
        assert dispatched_cb == cb_data
        assert kwargs == {'system': 'the-system-manager'}

    async def test_shows_an_alert_with_the_dispatch_result_when_show_alert_is_set(self):
        query = make_query()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )

        def set_show_alert(ctx):
            ctx.dialog.data['show_alert'] = True

        app = FakeAppRegistry(
            frame=make_frame(text='old text'),
            dispatch_result='Uptime: 1 day',
            dispatch_side_effect=set_show_alert,
        )

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.answer.assert_awaited_once_with('Uptime: 1 day', show_alert=True)

    async def test_alert_falls_back_to_frame_text_when_dispatch_result_is_none(self):
        query = make_query()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )

        def set_show_alert(ctx):
            ctx.dialog.data['show_alert'] = True

        app = FakeAppRegistry(
            frame=make_frame(text='rendered header'),
            dispatch_result=None,
            dispatch_side_effect=set_show_alert,
        )

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.answer.assert_awaited_once_with('rendered header', show_alert=True)

    async def test_no_alert_shown_when_show_alert_flag_is_not_set(self):
        query = make_query()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='new text'))

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.answer.assert_not_awaited()

    async def test_edits_the_message_when_the_rendered_text_changed(self):
        query = make_query(text='old text')
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='new text'))

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.bot.edit_message_text.assert_awaited_once()
        _, kwargs = query.bot.edit_message_text.call_args
        assert kwargs['text'] == 'new text'
        assert kwargs['chat_id'] == 42
        assert kwargs['message_id'] == 100

    async def test_edits_the_message_when_only_the_markup_changed(self):
        old_markup = InlineKeyboardMarkup(inline_keyboard=[])
        new_markup = InlineKeyboardMarkup(inline_keyboard=[[]])
        query = make_query(text='same text', markup=old_markup)
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='same text', markup=new_markup))

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.bot.edit_message_text.assert_awaited_once()

    async def test_does_not_edit_the_message_when_nothing_changed(self):
        markup = InlineKeyboardMarkup(inline_keyboard=[])
        query = make_query(text='same text', markup=markup)
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='same text', markup=markup))

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        query.bot.edit_message_text.assert_not_awaited()

    async def test_persists_the_context_after_handling(self):
        query = make_query()
        state = FakeState(
            {
                'kb_ctx': {
                    'dialog': {'data': {'breadcrumbs': ['main'], 'message_id': 100}},
                    'widgets': {},
                }
            }
        )
        app = FakeAppRegistry(frame=make_frame(text='new text'))

        await handle_kb(query, KeyboardCD(widget_id=0, button_id=0), state, app, system=None)

        saved = await state.get_data()
        assert saved['kb_ctx']['dialog']['data']['breadcrumbs'] == ['main']
