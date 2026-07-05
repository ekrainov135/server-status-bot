from abc import ABC, abstractmethod

from ..components.header import EMPTY_TEXT, Header
from ..components.widget import Widget
from ..models import KeyboardContext, KeyboardFrame


class BaseKeyboard(ABC):
    def __init__(
        self,
        header: Header | None = None,
        widgets: list[list[Widget]] | None = None,
    ) -> None:
        self._header = header or Header(EMPTY_TEXT)
        self._widgets = widgets or []

    @abstractmethod
    async def render(
        self,
        context: KeyboardContext,
        strings: dict[str, str],
    ) -> KeyboardFrame:
        pass
