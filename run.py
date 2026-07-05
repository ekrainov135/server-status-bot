import asyncio
import logging
from functools import partial

from aiogram import Bot

from app.bot.app_registry import AppRegistry
from app.bot.controller import LongPollingController
from app.bot.routers import get_routers
from app.settings import (
    CONF_DIR,
    INNER_MIDDLEWARES,
    LOCALES,
    LOG_FORMAT,
    OUTER_MIDDLEWARES,
    SERVICE_LIST,
    TOKEN,
)
from app.system import SystemManager, is_exists
from lib.aiogram_keyboard.models import KeyboardContext


def nav_vars(ctx: KeyboardContext, services: list[str]) -> dict:
    return {
        'lang': ctx.dialog.data.get('lang', 'ru'),
        'services': services,
    }


logger = logging.getLogger(__name__)


async def main() -> None:
    services = [service for service in SERVICE_LIST if await is_exists(service)]
    logger.info('Detected services: %s', services)

    app_registry = AppRegistry(
        nav_config=CONF_DIR / 'nav.yaml.j2',
        header_config=CONF_DIR / 'header.yaml.j2',
        widgets_config=CONF_DIR / 'widgets.yaml.j2',
        locales=LOCALES,
        vars_hook=partial(nav_vars, services=services),
    )

    system_manager = SystemManager(services)

    routers = get_routers()
    bot = Bot(token=TOKEN)

    controller = LongPollingController(
        bot=bot,
        routers=routers,
        app=app_registry,
        system=system_manager,
        inner_middlewares=INNER_MIDDLEWARES,
        outer_middlewares=OUTER_MIDDLEWARES,
    )

    await controller.run()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
    )
    asyncio.run(main())
