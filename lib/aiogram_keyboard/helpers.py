from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from .models import KeyboardContext


@runtime_checkable
class StateProtocol(Protocol):
    async def get_data(self) -> dict[str, Any]: ...
    async def update_data(self, **kwargs: Any) -> dict[str, Any]: ...


async def load_context(
    getter: Callable[[], Awaitable[dict[str, Any]]],
    key: str = 'kb_ctx',
) -> KeyboardContext:
    raw = await getter()
    ctx_data = raw.get(key)
    if ctx_data is None:
        return KeyboardContext()
    return KeyboardContext.load(ctx_data)


async def save_context(
    setter: Callable[..., Awaitable[Any]],
    context: KeyboardContext,
    key: str = 'kb_ctx',
) -> None:
    await setter(**{key: context.dump()})


class KeyboardSession:
    """Loads a `KeyboardContext` from FSM storage on enter and saves
    it back on exit.

    Wraps handler logic so dialog/widget state persists across
    messages without manual (de)serialization at each call site.
    """

    def __init__(self, state: StateProtocol, key: str = 'kb_ctx') -> None:
        self._state = state
        self._key = key
        self._context: KeyboardContext | None = None

    async def __aenter__(self) -> KeyboardContext:
        self._context = await load_context(self._state.get_data, self._key)
        return self._context

    async def __aexit__(
        self,
        exc_type: type,
        exc_val: BaseException,
        exc_tb: object,
    ) -> None:
        if exc_type is None and self._context is not None:
            await save_context(self._state.update_data, self._context, self._key)
