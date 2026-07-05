"""Tests for the concrete domain widgets in `app.bot.widgets`.

`is_active` is patched at its usage site (`app.bot.widgets.is_active`,
imported via `from app.system import ... is_active`) rather than at its
definition site, per the standard "patch where it's looked up" rule.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from app.bot.widgets import CommandExecWidget, ServiceManager, SwitchLocale, Transition
from lib.aiogram_keyboard.models import ButtonCallback, Dialog, WidgetCtx

STRINGS = {'start': 'Start', 'restart': 'Restart', 'stop': 'Stop'}


class TestTransition:
    async def test_pushes_a_new_screen_onto_breadcrumbs(self):
        transition = Transition(value='services')
        dialog = Dialog(data={'breadcrumbs': ['main']})

        await transition.on_push(0, WidgetCtx(), dialog)

        assert dialog.data['breadcrumbs'] == ['main', 'services']

    async def test_returning_to_an_already_visited_screen_truncates_breadcrumbs(self):
        transition = Transition(value='main')
        dialog = Dialog(data={'breadcrumbs': ['main', 'services', 'settings']})

        await transition.on_push(0, WidgetCtx(), dialog)

        assert dialog.data['breadcrumbs'] == ['main']

    async def test_returning_to_a_middle_screen_drops_everything_after_it(self):
        transition = Transition(value='services')
        dialog = Dialog(data={'breadcrumbs': ['main', 'services', 'settings']})

        await transition.on_push(0, WidgetCtx(), dialog)

        assert dialog.data['breadcrumbs'] == ['main', 'services']

    async def test_navigating_to_the_current_screen_is_a_no_op(self):
        transition = Transition(value='main')
        dialog = Dialog(data={'breadcrumbs': ['main']})

        await transition.on_push(0, WidgetCtx(), dialog)

        assert dialog.data['breadcrumbs'] == ['main']


class TestSwitchLocale:
    def test_constructor_advances_past_the_given_language(self):
        widget = SwitchLocale(value='ru', langs=['ru', 'en'])

        assert widget._value == 'en'

    def test_constructor_wraps_around_after_the_last_language(self):
        widget = SwitchLocale(value='en', langs=['ru', 'en'])

        assert widget._value == 'ru'

    async def test_on_push_sets_dialog_lang_to_the_buttons_current_value(self):
        widget = SwitchLocale(value='ru', langs=['ru', 'en'])  # _value is now 'en'
        dialog = Dialog(data={})
        widget_ctx = WidgetCtx(button_cb={0: ButtonCallback(action='push', value='en')})

        await widget.on_push(0, widget_ctx, dialog)

        assert dialog.data['lang'] == 'en'

    async def test_on_push_advances_the_button_to_the_next_language(self):
        widget = SwitchLocale(value='ru', langs=['ru', 'en'])  # _value is now 'en'
        dialog = Dialog(data={})
        widget_ctx = WidgetCtx(button_cb={0: ButtonCallback(action='push', value='en')})

        await widget.on_push(0, widget_ctx, dialog)

        # Wrapped back around to 'ru' after 'en' (last in the list).
        assert widget._value == 'ru'
        assert widget_ctx.button_cb[0].value == 'ru'

    async def test_two_consecutive_pushes_cycle_through_all_languages(self):
        widget = SwitchLocale(value='ru', langs=['ru', 'en', 'de'])  # _value -> 'en'
        dialog = Dialog(data={})
        widget_ctx = WidgetCtx(button_cb={0: ButtonCallback(action='push', value='en')})

        await widget.on_push(0, widget_ctx, dialog)
        assert dialog.data['lang'] == 'en'
        assert widget._value == 'de'

        widget_ctx.button_cb[0] = ButtonCallback(action='push', value=widget._value)
        await widget.on_push(0, widget_ctx, dialog)
        assert dialog.data['lang'] == 'de'
        assert widget._value == 'ru'


class TestCommandExecWidgetOnPush:
    async def test_forwards_the_configured_value_as_the_callable_name(self):
        widget = CommandExecWidget(value='uptime', label_key='check_uptime')
        system_manager = AsyncMock()
        system_manager.get_exec_result.return_value = '1 day, 2:00:00'

        result = await widget.on_push(0, WidgetCtx(), Dialog(data={}), system=system_manager)

        assert result == '1 day, 2:00:00'
        callable_name = system_manager.get_exec_result.call_args.args[0]
        assert callable_name == 'uptime'

    async def test_sets_show_alert_flag_on_the_dialog_when_configured(self):
        widget = CommandExecWidget(value='uptime', show_alert=True)
        system_manager = AsyncMock()
        system_manager.get_exec_result.return_value = '1 day'
        dialog = Dialog(data={})

        await widget.on_push(0, WidgetCtx(), dialog, system=system_manager)

        assert dialog.data['show_alert'] is True

    async def test_does_not_set_show_alert_flag_by_default(self):
        widget = CommandExecWidget(value='uptime')
        system_manager = AsyncMock()
        system_manager.get_exec_result.return_value = '1 day'
        dialog = Dialog(data={})

        await widget.on_push(0, WidgetCtx(), dialog, system=system_manager)

        assert 'show_alert' not in dialog.data

    async def test_extra_constructor_kwargs_leak_through_to_the_target_handler(self):
        widget = CommandExecWidget(
            value='status_summary', label_key='check_network', name='network'
        )
        system_manager = AsyncMock()
        system_manager.get_exec_result.return_value = 'ok'

        await widget.on_push(0, WidgetCtx(), Dialog(data={}), system=system_manager)

        _, forwarded_kwargs = system_manager.get_exec_result.call_args
        assert forwarded_kwargs == {
            'label_key': 'check_network',
            'value': 'status_summary',
            'name': 'network',
        }


class TestServiceManagerBuildSpecs:
    @patch('app.bot.widgets.is_active')
    async def test_offers_restart_when_the_service_is_currently_active(self, mock_is_active):
        mock_is_active.return_value = True
        widget = ServiceManager(name='nginx')

        specs = await widget._build_specs(
            strings=STRINGS, widget_ctx=WidgetCtx(), dialog_ctx=Dialog()
        )

        assert [spec.action for spec in specs[0]] == ['info', 'restart', 'stop']
        mock_is_active.assert_called_once_with('nginx')

    @patch('app.bot.widgets.is_active')
    async def test_offers_start_when_the_service_is_currently_inactive(self, mock_is_active):
        mock_is_active.return_value = False
        widget = ServiceManager(name='nginx')

        specs = await widget._build_specs(
            strings=STRINGS, widget_ctx=WidgetCtx(), dialog_ctx=Dialog()
        )

        assert [spec.action for spec in specs[0]] == ['info', 'start', 'stop']

    @patch('app.bot.widgets.is_active')
    async def test_every_button_carries_the_service_name_as_its_value(self, mock_is_active):
        mock_is_active.return_value = False
        widget = ServiceManager(name='nginx')

        specs = await widget._build_specs(
            strings=STRINGS, widget_ctx=WidgetCtx(), dialog_ctx=Dialog()
        )

        assert all(spec.value == 'nginx' for spec in specs[0])


class TestServiceManagerActions:
    async def test_on_start_delegates_to_system_manager_service(self):
        widget = ServiceManager(name='nginx')
        system_manager = MagicMock()

        await widget.on_start(1, WidgetCtx(), Dialog(), system=system_manager)

        system_manager.service.assert_called_once_with('nginx')
        system_manager.service.return_value.start.assert_called_once()

    async def test_on_restart_delegates_to_system_manager_service(self):
        widget = ServiceManager(name='fail2ban')
        system_manager = MagicMock()

        await widget.on_restart(1, WidgetCtx(), Dialog(), system=system_manager)

        system_manager.service.assert_called_once_with('fail2ban')
        system_manager.service.return_value.restart.assert_called_once()

    async def test_on_stop_delegates_to_system_manager_service(self):
        widget = ServiceManager(name='ufw')
        system_manager = MagicMock()

        await widget.on_stop(1, WidgetCtx(), Dialog(), system=system_manager)

        system_manager.service.assert_called_once_with('ufw')
        system_manager.service.return_value.stop.assert_called_once()

    async def test_on_info_is_a_no_op(self):
        widget = ServiceManager(name='nginx')
        system_manager = MagicMock()

        result = await widget.on_info(0, WidgetCtx(), Dialog(), system=system_manager)

        assert result is None
        system_manager.service.assert_not_called()
