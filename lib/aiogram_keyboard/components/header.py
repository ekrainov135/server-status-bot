from collections.abc import Callable

from ..models import Dialog

EMPTY_TEXT = chr(12644) * 10


class Header:
    """Renders a keyboard screen's header text.

    Configured with either a static string key looked up in `strings`,
    or a callable for dynamic content (e.g. live system info). Falls
    back to an invisible placeholder (`EMPTY_TEXT`) since Telegram
    messages cannot have empty text.
    """

    def __init__(
        self,
        text: str | None = None,
        fn: Callable[[dict[str, str], Dialog], str] | None = None,
    ) -> None:
        if (text is None) == (fn is None):
            raise ValueError()
        self._text = text
        self._fn = fn

    def render(
        self,
        strings: dict[str, str],
        dialog_ctx: Dialog,
    ) -> str:
        if self._text:
            return strings.get(self._text, self._text)
        elif self._fn:
            return self._fn(strings, dialog_ctx)
        return EMPTY_TEXT
