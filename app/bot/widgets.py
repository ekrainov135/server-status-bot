from typing import cast

from app.system import SystemManager, is_active
from lib.aiogram_keyboard.components.widget import Button, ButtonSpec, Widget, WidgetCtx
from lib.aiogram_keyboard.models import Dialog


class Transition(Button):
    """Navigates to another screen, mimicking browser-style back
    navigation.

    If the target screen is already in the breadcrumb trail, navigates
    back to it (truncating everything after); otherwise pushes it as a
    new screen.
    """

    async def on_push(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs,
    ) -> None:
        if self._value in dialog_ctx.data['breadcrumbs']:
            dialog_ctx.data['breadcrumbs'] = dialog_ctx.data['breadcrumbs'][
                : dialog_ctx.data['breadcrumbs'].index(self._value) + 1
            ]
        else:
            dialog_ctx.data['breadcrumbs'].append(self._value)


class SwitchLocale(Button):
    def __init__(
        self,
        value: str,
        label_key: str | None = None,
        langs: list[str] | None = None,
        *args,
        **kwargs,
    ):
        self._langs = langs or []
        super().__init__(self._next_lang(value), label_key, *args, **kwargs)

    def _next_lang(self, lang: str) -> str:
        idx = self._langs.index(lang)
        return self._langs[idx + 1] if idx < len(self._langs) - 1 else self._langs[0]

    async def on_push(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs,
    ) -> None:
        dialog_ctx.data['lang'] = self._value
        widget_ctx.button_cb[button_id].value = self._value = self._next_lang(self._value)


class CommandExecWidget(Button):
    """Button that runs a registered system command on push.

    Note: any constructor kwargs not consumed here (including
    `label_key`/`value`) are stored and forwarded as-is to the target
    handler's call, so handlers must accept `**kwargs`.
    """

    def __init__(self, *args, show_alert: bool = False, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._kwargs = kwargs
        self.show_alert = show_alert

    async def on_push(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> str | None:
        system_manager = cast(SystemManager, kwargs['system'])
        result = await system_manager.get_exec_result(self._value, **self._kwargs)
        if self.show_alert:
            dialog_ctx.data['show_alert'] = True
        return result


class ServiceManager(Widget):
    def __init__(self, name: str) -> None:
        self._name = name

    async def _build_specs(
        self,
        strings: dict[str, str],
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
    ) -> list[list[ButtonSpec]]:
        start_or_restart = 'restart' if await is_active(self._name) else 'start'

        return [
            [
                ButtonSpec(
                    label=strings.get(self._name, self._name),
                    button_id=0,
                    action='info',
                    value=self._name,
                ),
                ButtonSpec(
                    label=strings[start_or_restart],
                    button_id=1,
                    action=start_or_restart,
                    value=self._name,
                ),
                ButtonSpec(
                    label=strings['stop'],
                    button_id=2,
                    action='stop',
                    value=self._name,
                ),
            ]
        ]

    async def on_info(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> None:
        pass

    async def on_start(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> None:
        system_manager = cast(SystemManager, kwargs['system'])
        system_manager.service(self._name).start()

    async def on_restart(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> None:
        system_manager = cast(SystemManager, kwargs['system'])
        system_manager.service(self._name).restart()

    async def on_stop(
        self,
        button_id: int,
        widget_ctx: WidgetCtx,
        dialog_ctx: Dialog,
        **kwargs: dict,
    ) -> None:
        system_manager = cast(SystemManager, kwargs['system'])
        system_manager.service(self._name).stop()
