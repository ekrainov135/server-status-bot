from aiogram.types import InlineKeyboardMarkup

from lib.aiogram_keyboard.keyboards.base import BaseKeyboard
from lib.aiogram_keyboard.models import KeyboardContext, KeyboardFrame, WidgetCtx


class InlineKeyboard(BaseKeyboard):
    async def render(
        self,
        context: KeyboardContext,
        strings: dict[str, str],
    ) -> KeyboardFrame:
        """Build the keyboard markup and header text for the current screen.

        Widgets sharing a row only contribute their first button row to
        the merged row; producing multiple rows is only possible when a
        widget is alone in its `row_group`.
        """

        all_rows = []
        widget_id = 0

        for row_group in self._widgets:
            context.widgets.setdefault(widget_id, WidgetCtx())

            if len(row_group) == 1:
                # Single widget — may produce multiple button rows
                widget = row_group[0]
                widget_ctx = context.widgets.setdefault(widget_id, WidgetCtx())
                button_rows = await widget.render(widget_id, strings, widget_ctx, context.dialog)
                all_rows.extend(button_rows)
                widget_id += 1
            else:
                # Multiple widgets — merge their first rows into one keyboard row
                merged = []
                for widget in row_group:
                    widget_ctx = context.widgets.setdefault(widget_id, WidgetCtx())
                    button_rows = await widget.render(
                        widget_id, strings, widget_ctx, context.dialog
                    )
                    merged.extend(button_rows[0])
                    widget_id += 1
                all_rows.append(merged)

        header = self._header.render(strings, context.dialog)

        return KeyboardFrame(
            text=header,
            markup=InlineKeyboardMarkup(inline_keyboard=all_rows),
            context=context,
        )
