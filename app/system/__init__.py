import inspect
from typing import cast

from .handlers import CONFIG, SYSTEM_HANDLERS
from .metrics.utils import subprocess_run


async def is_exists(name: str) -> bool:
    return cast(
        bool, await subprocess_run(CONFIG['sh']['is_service_exists'].format(name=name), 'ok')
    )


async def is_active(name: str) -> bool:
    return cast(
        bool, await subprocess_run(CONFIG['sh']['is_service_active'].format(name=name), 'ok')
    )


async def is_enabled(name: str) -> bool:
    return cast(
        bool, await subprocess_run(CONFIG['sh']['is_service_enabled'].format(name=name), 'ok')
    )


class Service:
    def __init__(self, name: str):
        self._name = name

    async def start(self, *args):
        return await subprocess_run(CONFIG['sh']['service_start'].format(name=self._name))

    async def restart(self, *args):
        return await subprocess_run(CONFIG['sh']['service_restart'].format(name=self._name))

    async def stop(self, *args):
        return await subprocess_run(CONFIG['sh']['service_stop'].format(name=self._name))


class SystemManager:
    def __init__(self, services: list[str]):
        self.services = services

    @staticmethod
    def service(name: str):
        return Service(name)

    @staticmethod
    async def get_exec_result(callable_name: str, **kwargs) -> str | None:
        callable_obj = SYSTEM_HANDLERS[callable_name]

        if inspect.iscoroutinefunction(callable_obj):
            return cast(str | None, await callable_obj(**kwargs))
        elif inspect.isfunction(callable_obj):
            return cast(str | None, callable_obj(**kwargs))
        else:
            raise AttributeError()
