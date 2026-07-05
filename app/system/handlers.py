"""System command handlers, registered by name.

Each function decorated with `@register(SYSTEM_HANDLERS, name)` is called
one of two ways, depending on where it's referenced from config:

- As a command (`value: name` in a widget config): called as
  `callable(**kwargs)`, where `kwargs` includes `system=<SystemManager>`.
- As a screen header (`callable: name` in header.yaml.j2): called
  positionally as `callable(strings, dialog)`.

`host_info` is the only handler currently used as a header; it accepts
`*args, **kwargs` to satisfy both call conventions.
"""

import platform
import socket
from collections.abc import Callable
from datetime import timedelta as td
from time import time
from typing import cast

import psutil

import app.system.metrics.hardware  # noqa: F401
import app.system.metrics.network  # noqa: F401

from .metrics import REGISTRY as METRICS_REGISTRY
from .metrics.utils import load_config, register, subprocess_run

SYSTEM_HANDLERS: dict[str, Callable] = {}
CONFIG = load_config()


@register(SYSTEM_HANDLERS, 'status_summary')
async def get_status_summary(name: str, **kwargs) -> str:
    handler = METRICS_REGISTRY[name]

    return cast(str, await handler(CONFIG))


@register(SYSTEM_HANDLERS, 'reboot')
async def reboot(**kwargs):
    await subprocess_run(CONFIG['sh']['reboot'])


@register(SYSTEM_HANDLERS, 'uptime')
def get_uptime(**kwargs) -> str:
    return str(td(seconds=int(time() - psutil.boot_time())))


@register(SYSTEM_HANDLERS, 'host_info')
def get_host_info(*args, **kwargs) -> str:
    return f'{platform.system()}@{socket.gethostname()}'
