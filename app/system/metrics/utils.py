from __future__ import annotations

import asyncio
import os
import platform
from collections.abc import Callable
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / 'config.yaml'
UNKNOWN_VALUE = '???'


def load_config() -> dict:
    with open(_CONFIG_PATH, encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def is_root() -> bool:
    return os.geteuid() == 0


def get_os_name() -> str:
    system = platform.system().lower()

    if system == 'darwin':
        return 'macos'

    return system


def fmt_gib(num_bytes: int, precision: int = 2) -> str:
    return f'{num_bytes / (1024**3):.{precision}f}G'


def register(mapping: dict, name: str) -> Callable:
    """Decorator that adds a function to a registry dict under `name`.

    Used to plug new metrics into `app.system.metrics.REGISTRY` and new
    system commands into `app.system.handlers.SYSTEM_HANDLERS`; the
    registered `name` is what config files reference via `value:`.
    """

    def decorator(fn: Callable) -> Callable:
        mapping[name] = fn
        return fn

    return decorator


async def subprocess_run(script: str, stdout_validation: str | None = None) -> bool | None:
    cmd = ['sh', '-c', script]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        return None

    if stdout_validation:
        return stdout.decode().strip() == stdout_validation

    return None
