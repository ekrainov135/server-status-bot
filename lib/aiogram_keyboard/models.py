from dataclasses import dataclass
from typing import Any

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from pydantic import BaseModel, Field


class ButtonCallback(BaseModel):
    action: str
    value: Any = None


class WidgetCtx(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    button_cb: dict[int, ButtonCallback] = Field(default_factory=dict)


class Dialog(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class KeyboardContext(BaseModel):
    dialog: Dialog = Field(default_factory=Dialog)
    widgets: dict[int, WidgetCtx] = Field(default_factory=dict)

    def dump(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def load(cls, raw: dict[str, Any]) -> KeyboardContext:
        return cls.model_validate(raw)


class KeyboardCD(CallbackData, prefix='kb'):
    widget_id: int
    button_id: int


@dataclass
class KeyboardFrame:
    text: str
    markup: InlineKeyboardMarkup
    context: KeyboardContext
