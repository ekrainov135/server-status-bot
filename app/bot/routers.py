from aiogram import Router
from aiogram.filters import CommandStart

from app.bot import handlers
from lib.aiogram_keyboard.models import KeyboardCD


def get_routers() -> list[Router]:
    main_router = Router()

    main_router.message.register(handlers.cmd_start, CommandStart())
    main_router.callback_query.register(handlers.handle_kb, KeyboardCD.filter())

    return [main_router]
