import logging

from aiogram import BaseMiddleware, Bot, Dispatcher, Router
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.strategy import FSMStrategy

logger = logging.getLogger(__name__)


class LongPollingController:
    def __init__(
        self,
        bot: Bot,
        routers: list[Router],
        storage: BaseStorage | None = None,
        inner_middlewares: list[BaseMiddleware] | None = None,
        outer_middlewares: list[BaseMiddleware] | None = None,
        run_params: dict | None = None,
        **dp_kwargs,
    ):
        storage = storage or MemoryStorage()

        self.bot = bot
        self.run_params = run_params or {}

        self.dp = Dispatcher(storage=storage, fsm_strategy=FSMStrategy.CHAT, **dp_kwargs)
        self.dp.include_routers(*routers)

        for middleware in outer_middlewares or []:
            self.dp.update.outer_middleware(middleware)
        for middleware in inner_middlewares or []:
            self.dp.update.middleware(middleware)

        self.dp.startup.register(self.on_startup)
        self.dp.shutdown.register(self.on_shutdown)

    @staticmethod
    async def on_startup():
        logger.info('Bot started, polling for updates')

    async def on_shutdown(self):
        logger.info('Bot shutting down')
        await self.bot.session.close()

    async def run(self):
        if self.run_params.get('skip_updates'):
            await self.bot.delete_webhook(drop_pending_updates=True)

        await self.dp.start_polling(
            self.bot,
            # tasks_concurrency_limit=self.run_params.get('tasks_concurrency_limit'),
            # allowed_updates=self.run_params.get('allowed_updates'),
        )
