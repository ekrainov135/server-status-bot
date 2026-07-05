from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from aiogram.types import InlineKeyboardButton

from ..models import ButtonCallback, Dialog, KeyboardCD, WidgetCtx


@dataclass
class ButtonSpec:
    label: str
    button_id: int
    action: str
    value: Any = None


class Widget(ABC):
    """Base class for all keyboard widgets.

    Subclasses implement `_build_specs` to describe their buttons.
    Button actions are routed dynamically: pressing a button with
    action="foo" calls `on_foo` on the widget, so subclasses add new
    behaviour simply by defining `on_<action>` methods.
    """

    @abstractmethod
    async def _build_specs(
        self,
        strings: dict[str, str],
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
    ) -> list[list[ButtonSpec]]:
        pass

    async def render(
        self,
        widget_id: int,
        strings: dict[str, str],
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
    ) -> list[list[InlineKeyboardButton]]:
        specs = await self._build_specs(strings, widget_ctx, dialog_ctx)
        rows: list[list[InlineKeyboardButton]] = []

        for spec_row in specs:
            row: list[InlineKeyboardButton] = []
            for spec in spec_row:
                # Register callback metadata for later dispatch
                widget_ctx.button_cb[spec.button_id] = ButtonCallback(
                    action=spec.action,
                    value=spec.value,
                )
                packed = KeyboardCD(
                    widget_id=widget_id,
                    button_id=spec.button_id,
                ).pack()
                row.append(
                    InlineKeyboardButton(
                        text=spec.label,
                        callback_data=packed,
                    )
                )
            rows.append(row)

        return rows

    async def dispatch(
        self,
        action: str,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: Any,
    ) -> Any:
        handler = getattr(self, f'on_{action}', None)
        if handler is None:
            raise AttributeError()
        return await handler(button_id, widget_ctx, dialog_ctx, **kwargs)


class Button(Widget):
    """Single-button widget with one built-in "push" action.

    Subclass and override `on_push` to react to the button being
    pressed; this is the base for most concrete widgets in
    `app.bot.widgets`.
    """

    def __init__(self, value: str, label_key: str | None = None, *args, **kwargs) -> None:
        self._value = value
        self._label_key = label_key or value

    async def _build_specs(
        self,
        strings: dict[str, str],
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
    ) -> list[list[ButtonSpec]]:
        return [
            [
                ButtonSpec(
                    label=strings.get(self._label_key, self._label_key),
                    button_id=0,
                    action='push',
                    value=self._value,
                )
            ]
        ]

    async def on_push(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> Any:
        pass
