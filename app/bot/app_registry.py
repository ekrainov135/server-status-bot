from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import jinja2
import yaml

from app.system.handlers import SYSTEM_HANDLERS
from lib.aiogram_keyboard.components.header import EMPTY_TEXT, Header
from lib.aiogram_keyboard.components.widget import Widget
from lib.aiogram_keyboard.keyboards.inline import InlineKeyboard
from lib.aiogram_keyboard.models import KeyboardCD, KeyboardContext, KeyboardFrame

from .widgets import Transition


def _load_attr(class_path: str) -> Any:
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class AppRegistry:
    """Builds bot screens from Jinja2-templated YAML config.

    Screens and navigation are declared in `nav_config`, headers in
    `header_config`, and widget instances (by dotted class path) in
    `widgets_config`. A cell name prefixed with `widget__` is
    instantiated from `widgets_config`; any other name becomes a plain
    `Transition` to that screen. This is the main extension point for
    adding new screens/widgets without touching Python code.
    """

    WIDGET_PREFIX = 'widget__'

    def __init__(
        self,
        nav_config: str | Path,
        header_config: str | Path,
        widgets_config: str | Path,
        locales: dict[str, dict[str, str]],
        vars_hook: Callable[[KeyboardContext], dict[str, Any]],
    ) -> None:
        self._nav_template = jinja2.Template(Path(nav_config).read_text(encoding='utf-8'))
        self._header_template = jinja2.Template(Path(header_config).read_text(encoding='utf-8'))
        self._widgets_template = jinja2.Template(Path(widgets_config).read_text(encoding='utf-8'))

        self._locales = locales
        self._vars_hook = vars_hook

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _instantiate_cell(
        self, cell: str, raw_widgets: dict | None = None, render_vars: dict | None = None
    ) -> Widget:
        """Instantiate the widget (or transition) for a single nav cell.

        Exactly one of `raw_widgets` (already-parsed config) or
        `render_vars` (used to render `widgets_config` on demand) must be
        given, depending on whether the caller already has parsed config.
        """

        if raw_widgets is None and render_vars is None:
            raise AttributeError()

        if cell.startswith(self.WIDGET_PREFIX):
            if render_vars:
                widgets_rendered = self._widgets_template.render(**render_vars)
                raw_widgets = yaml.safe_load(widgets_rendered) or {}

            widget_conf = dict(cast(dict[str, Any], raw_widgets)[cell])
            cls = cast(type[Widget], _load_attr(widget_conf.pop('class')))
            return cls(**widget_conf)
        else:
            return Transition(value=cell)

    def _build_widget(
        self,
        widget_id: int,
        render_vars: dict[str, Any],
        kb_name: str,
    ) -> Widget:
        nav_rendered = self._nav_template.render(**render_vars)
        kb_rows: list[list[str]] = yaml.safe_load(nav_rendered).get(kb_name)

        flat_cells = [cell for row in kb_rows for cell in row]
        cell = flat_cells[widget_id]

        return self._instantiate_cell(cell, render_vars=render_vars)

    def _build_keyboard(self, render_vars: dict[str, Any], kb_name: str) -> InlineKeyboard:
        # Navigation mapping
        navigation_rendered = self._nav_template.render(**render_vars)
        kb_rows: list[list[str]] = yaml.safe_load(navigation_rendered).get(kb_name)

        # Keyboard header text
        header_rendered = self._header_template.render(**render_vars)
        kb_text_data = (yaml.safe_load(header_rendered) or {}).get(kb_name)
        if kb_text_data and 'callable' in kb_text_data:
            kb_header = Header(fn=SYSTEM_HANDLERS[kb_text_data.pop('callable')])
        elif kb_text_data and 'text' in kb_text_data:
            kb_text = kb_text_data.pop('text')
            kb_header = Header(
                fn=cast(Callable[[dict[str, str], object], str], lambda s, d, k=kb_text: s[k])
            )
        else:
            kb_header = Header(text=EMPTY_TEXT)

        # Keyboards widgets
        widgets_rendered = self._widgets_template.render(**render_vars)
        raw_widgets: dict[str, Any] = yaml.safe_load(widgets_rendered) or {}

        # Markup rows
        markup_rows: list[list[Widget]] = []
        for row_cells in kb_rows:
            row: list[Widget] = []
            for cell in row_cells:
                widget = self._instantiate_cell(cell, raw_widgets=raw_widgets)
                row.append(widget)
            markup_rows.append(row)

        return InlineKeyboard(
            header=kb_header,
            widgets=markup_rows,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, render_vars: dict[str, Any]) -> None:
        """Instantiate every widget on every screen once, eagerly.

        Fails fast at startup with a clear error instead of failing when a
        specific button is pressed. Call once after construction with
        `render_vars` representative of a real session (e.g. default lang
        and the actually detected services).
        """

        nav_rendered = self._nav_template.render(**render_vars)
        screens: dict[str, list[list[str]]] = yaml.safe_load(nav_rendered) or {}

        for kb_name in screens:
            try:
                self._build_keyboard(render_vars, kb_name)
            except Exception as exc:
                raise RuntimeError(f"Invalid config for screen '{kb_name}': {exc}") from exc

    async def dispatch(
        self,
        cb_data: KeyboardCD,
        ctx: KeyboardContext,
        **kwargs: Any,
    ) -> Any:
        """Route a CallbackQuery to the correct keyboard's dispatch()."""
        vars_hook = self._vars_hook(ctx)
        kb_name = ctx.dialog.data['breadcrumbs'][-1]
        widget_ctx = ctx.widgets[cb_data.widget_id]
        widget = self._build_widget(cb_data.widget_id, vars_hook, kb_name)
        result = await widget.dispatch(
            widget_ctx.button_cb[cb_data.button_id].action,
            cb_data.button_id,
            widget_ctx,
            ctx.dialog,
            **kwargs,
        )
        return result

    async def render(self, ctx: KeyboardContext) -> KeyboardFrame:
        vars_hook = self._vars_hook(ctx)
        keyboard = self._build_keyboard(vars_hook, ctx.dialog.data['breadcrumbs'][-1])
        strings = self._locales[vars_hook['lang']]
        return await keyboard.render(ctx, strings)
