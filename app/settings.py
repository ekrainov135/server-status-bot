import os
from pathlib import Path

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from dotenv import load_dotenv

from app.bot.middleware import AdminAccessMiddleware
from app.utils import load_yaml, merge_with_concat

ROOT_DIR = Path(__file__).resolve().parent.parent
CONF_DIR = ROOT_DIR / 'data' / 'bot' / 'configs'
STRINGS_DIR = ROOT_DIR / 'data' / 'bot' / 'strings'

load_dotenv(ROOT_DIR / '.env')


LOG_FORMAT = '%(asctime)s %(levelname)s %(name)s: %(message)s'

# TELEGRAM API SETTINGS
TOKEN = os.getenv('BOT_TOKEN', '').strip()
ALLOWED_USERS = [int(x) for x in os.getenv('ADMINS', '').split(',')]


# LOCALES
_common = load_yaml(STRINGS_DIR / 'common.yaml')
LOCALES: dict[str, dict[str, str]] = {
    lang: merge_with_concat(_common, load_yaml(STRINGS_DIR / f'{lang}.yaml'))
    for lang in ('ru', 'en')
}

SERVICE_LIST = ['ufw', 'fail2ban', 'ssh', 'sftp']


INNER_MIDDLEWARES: list[BaseMiddleware] = [
    AdminAccessMiddleware(ALLOWED_USERS),
]
OUTER_MIDDLEWARES: list[BaseMiddleware] = []
