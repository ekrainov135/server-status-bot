"""Tests for `app.bot.app_registry.AppRegistry`.

This is the most complex piece of the application: it renders Jinja2
templates into YAML on every call, dynamically instantiates widget classes
by dotted path, and wires the result into `lib.aiogram_keyboard` objects.
Rather than depending on this project's real `data/bot/configs/*.yaml.j2`
(which would make these tests brittle to unrelated content changes), each
test builds a minimal, self-contained config on disk via `tmp_path` and
exercises the registry against it -- using the project's *real* `Transition`
and `SwitchLocale` widgets so the tests also double as integration coverage
for how those widgets behave once wired through the registry.
"""

import textwrap
from copy import deepcopy

import pytest

from app.bot.app_registry import AppRegistry
from lib.aiogram_keyboard.models import Dialog, KeyboardCD, KeyboardContext

LOCALES = {
    'ru': {
        'main_header': '\u0413\u043b\u0430\u0432\u043d\u0430\u044f',
        'second_header': '\u042d\u043a\u0440\u0430\u043d \u043d\u043e\u043c\u0435\u0440 \u0434\u0432\u0430',
        'go_second': '\u041a \u0432\u0442\u043e\u0440\u043e\u043c\u0443',
        'main': '\u041d\u0430\u0437\u0430\u0434',
    },
    'en': {
        'main_header': 'Main',
        'second_header': 'Second screen',
        'go_second': 'To second',
        'main': 'Back',
    },
}


def _write_toy_configs(tmp_path, nav_yaml: str, widgets_yaml: str, text_yaml: str):
    nav = tmp_path / 'nav.yaml.j2'
    nav.write_text(textwrap.dedent(nav_yaml))

    widgets = tmp_path / 'widgets.yaml.j2'
    widgets.write_text(textwrap.dedent(widgets_yaml))

    text = tmp_path / 'text.yaml.j2'
    text.write_text(textwrap.dedent(text_yaml))

    return nav, text, widgets


BASIC_NAV = """\
    main:
      - [widget__go_second]
    second:
      - [main]
"""

BASIC_WIDGETS = """\
    widget__go_second:
      class: app.bot.widgets.Transition
      value: second
      label_key: go_second
"""

BASIC_TEXT = """\
    main:
      text: main_header
    second:
      text: second_header
"""


@pytest.fixture
def basic_registry(tmp_path):
    nav, text, widgets = _write_toy_configs(tmp_path, BASIC_NAV, BASIC_WIDGETS, BASIC_TEXT)
    return AppRegistry(
        nav_config=nav,
        header_config=text,
        widgets_config=widgets,
        locales=LOCALES,
        vars_hook=lambda ctx: {'lang': ctx.dialog.data.get('lang', 'ru')},
    )


basic_ctx = KeyboardContext(dialog=Dialog(data={'breadcrumbs': ['main']}))


class TestAppRegistryRender:
    async def test_renders_header_text_for_the_current_screen(self, basic_registry):
        ctx = deepcopy(basic_ctx)
        frame = await basic_registry.render(ctx)

        assert frame.text == '\u0413\u043b\u0430\u0432\u043d\u0430\u044f'

    async def test_renders_button_labels_from_widgets_config(self, basic_registry):
        ctx = deepcopy(basic_ctx)
        frame = await basic_registry.render(ctx)

        labels = [b.text for row in frame.markup.inline_keyboard for b in row]
        assert labels == ['\u041a \u0432\u0442\u043e\u0440\u043e\u043c\u0443']

    async def test_render_selects_locale_dict_via_vars_hook(self, basic_registry):
        ctx = deepcopy(basic_ctx)
        ctx.dialog.data['lang'] = 'en'

        frame = await basic_registry.render(ctx)

        assert frame.text == 'Main'

    async def test_bare_screen_name_cells_become_transition_widgets(self, basic_registry):
        """The `second` screen's only cell is `main` -- a plain screen name,
        not a `widget__*` id -- which `_instantiate_cell` turns into a
        `Transition(value='main')` on the fly.
        """
        ctx = deepcopy(basic_ctx)
        ctx.dialog.data['breadcrumbs'] = ['second']

        frame = await basic_registry.render(ctx)

        labels = [b.text for row in frame.markup.inline_keyboard for b in row]
        assert labels == ['\u041d\u0430\u0437\u0430\u0434']


class TestAppRegistryDispatch:
    async def test_dispatch_pushes_new_screen_onto_breadcrumbs(self, basic_registry):
        ctx = deepcopy(basic_ctx)
        await basic_registry.render(ctx)  # populates ctx.widgets[0].button_cb

        await basic_registry.dispatch(KeyboardCD(widget_id=0, button_id=0), ctx, system=None)

        assert ctx.dialog.data['breadcrumbs'] == ['main', 'second']

    async def test_render_after_dispatch_shows_the_new_screen(self, basic_registry):
        ctx = deepcopy(basic_ctx)
        await basic_registry.render(ctx)

        await basic_registry.dispatch(KeyboardCD(widget_id=0, button_id=0), ctx, system=None)
        frame = await basic_registry.render(ctx)

        assert (
            frame.text
            == '\u042d\u043a\u0440\u0430\u043d \u043d\u043e\u043c\u0435\u0440 \u0434\u0432\u0430'
        )

    async def test_dispatch_forwards_extra_kwargs_to_the_widget_handler(self, tmp_path):
        """Uses `CommandExecWidget` to verify that `**kwargs` passed to
        `dispatch()` (e.g. `system=<SystemManager>`) actually reaches the
        widget's `on_<action>` handler, since `Transition` alone doesn't
        exercise that code path (it ignores `**kwargs`).
        """
        nav, text, widgets = _write_toy_configs(
            tmp_path,
            nav_yaml='main:\n  - [widget__ping]\n',
            widgets_yaml=(
                'widget__ping:\n'
                '  class: app.bot.widgets.CommandExecWidget\n'
                '  value: uptime\n'
                '  label_key: main\n'
            ),
            text_yaml='main:\n  text: main_header\n',
        )
        registry = AppRegistry(
            nav_config=nav,
            header_config=text,
            widgets_config=widgets,
            locales=LOCALES,
            vars_hook=lambda ctx: {'lang': 'ru'},
        )
        ctx = deepcopy(basic_ctx)
        await registry.render(ctx)

        class FakeSystemManager:
            async def get_exec_result(self, callable_name, **kwargs):
                return f'ran:{callable_name}'

        result = await registry.dispatch(
            KeyboardCD(widget_id=0, button_id=0),
            ctx,
            system=FakeSystemManager(),
        )

        assert result == 'ran:uptime'


class TestAppRegistryDynamicNavigation:
    """Exercises the Jinja2-templated `nav.yaml.j2` for-loop pattern used by
    the real `services` screen -- the actual selling point of a
    config-driven navigation graph: the same template produces a different
    keyboard depending on `render_vars`.
    """

    @pytest.fixture
    def dynamic_registry(self, tmp_path):
        nav, text, widgets = _write_toy_configs(
            tmp_path,
            nav_yaml=(
                'services:\n'
                '  {% for service in services %}\n'
                '  - [widget__svc_{{ service }}]\n'
                '  {% endfor %}\n'
                '  - [main]\n'
            ),
            widgets_yaml=(
                '{% for service in services %}\n'
                'widget__svc_{{ service }}:\n'
                '  class: app.bot.widgets.Transition\n'
                '  value: main\n'
                '  label_key: main\n'
                '{% endfor %}\n'
            ),
            text_yaml='services:\n  text: main_header\n',
        )
        return AppRegistry(
            nav_config=nav,
            header_config=text,
            widgets_config=widgets,
            locales=LOCALES,
            vars_hook=lambda ctx: {'lang': 'ru', 'services': ctx.dialog.data.get('services', [])},
        )

    async def test_screen_has_one_button_per_installed_service(self, dynamic_registry):
        ctx = deepcopy(basic_ctx)
        ctx.dialog.data.update({'breadcrumbs': ['services'], 'services': ['nginx', 'ufw']})

        frame = await dynamic_registry.render(ctx)

        # 2 service rows + 1 "back to main" row
        assert len(frame.markup.inline_keyboard) == 3

    async def test_screen_has_no_service_buttons_when_no_services_installed(self, dynamic_registry):
        ctx = deepcopy(basic_ctx)
        ctx.dialog.data.update({'breadcrumbs': ['services'], 'services': []})

        frame = await dynamic_registry.render(ctx)

        # Only the "back to main" row remains.
        assert len(frame.markup.inline_keyboard) == 1


class TestInstantiateCellValidation:
    def test_raises_when_neither_argument_is_given(self, basic_registry):
        with pytest.raises(AttributeError):
            basic_registry._instantiate_cell('main')

    def test_succeeds_with_only_render_vars(self, basic_registry):
        widget = basic_registry._instantiate_cell('widget__go_second', render_vars={'lang': 'ru'})

        assert widget._value == 'second'

    def test_succeeds_with_only_raw_widgets(self, basic_registry):
        raw_widgets = {
            'widget__go_second': {'class': 'app.bot.widgets.Transition', 'value': 'second'}
        }

        widget = basic_registry._instantiate_cell('widget__go_second', raw_widgets=raw_widgets)

        assert widget._value == 'second'


def test_real_config_is_valid():
    """Regression test for the real project config files.

    Unlike `test_app_registry.py`, which intentionally uses toy configs to stay
    robust against unrelated content changes, this test targets the actual
    `data/bot/configs/*.yaml.j2` files on purpose: its whole point is to catch
    typos in widget classes, label keys, or screen names before they reach
    production.
    """

    from app.settings import CONF_DIR, LOCALES

    app = AppRegistry(
        nav_config=CONF_DIR / 'nav.yaml.j2',
        header_config=CONF_DIR / 'header.yaml.j2',
        widgets_config=CONF_DIR / 'widgets.yaml.j2',
        locales=LOCALES,
        vars_hook=lambda ctx: {},  # not used by validate() directly
    )

    # Representative vars: default language plus a sample service list,
    # since the real list depends on what's installed on the host.
    app.validate({'lang': 'ru', 'services': ['ufw', 'fail2ban', 'ssh', 'sftp']})
