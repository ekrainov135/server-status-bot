from __future__ import annotations

import asyncio
import json
import logging
from typing import cast

import psutil

from . import REGISTRY
from .utils import UNKNOWN_VALUE, fmt_gib, is_root, register

_CPU_SENSOR_KEYS = ('coretemp', 'k10temp', 'zenpower', 'cpu_thermal', 'acpitz')

logger = logging.getLogger(__name__)


def get_cpu_temp() -> str:
    try:
        sensors = psutil.sensors_temperatures()
        if not sensors:
            return UNKNOWN_VALUE
        for key in _CPU_SENSOR_KEYS:
            if key in sensors:
                vals = [e.current for e in sensors[key] if e.current and e.current > 0]
                if vals:
                    return f'{max(vals):.0f}°C'
    except AttributeError:
        pass
    return UNKNOWN_VALUE


def get_ram_temp() -> str:
    try:
        sensors = psutil.sensors_temperatures()
        for key in sensors:
            if any(sub in key.lower() for sub in ('dimm', 'ddr', 'memory')):
                vals = [e.current for e in sensors[key] if e.current and e.current > 0]
                if vals:
                    return f'{max(vals):.0f}°C'
    except AttributeError:
        pass
    return UNKNOWN_VALUE


async def _smartctl(*args: str) -> dict | None:
    cmd = ['smartctl', '-j', *args]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
    except FileNotFoundError:
        return None

    if proc.returncode != 0:
        return None

    return cast(dict, json.loads(stdout.decode()))


async def get_disk_temps() -> list[tuple[str, str]]:
    if not is_root():
        return [('disk', UNKNOWN_VALUE)]

    scan = await _smartctl('--scan')
    if not scan:
        logger.warning('smartctl scan failed or returned no devices')
        return [('disk', UNKNOWN_VALUE)]

    devices: list[dict] = scan.get('devices', [])
    if not devices:
        logger.warning('smartctl scan failed or returned no devices')
        return [('disk', UNKNOWN_VALUE)]

    results: list[tuple[str, str]] = []
    for dev in devices:
        path: str = dev.get('name', '')
        short = path.split('/')[-1]  # /dev/sda → sda, /dev/nvme0 → nvme0

        info = await _smartctl('-A', path)
        if not info:
            results.append((short, UNKNOWN_VALUE))
            continue

        temp = info.get('temperature', {}).get('current')
        results.append((short, f'{temp}°C' if temp is not None else UNKNOWN_VALUE))

    return results or [('disk', UNKNOWN_VALUE)]


# ─── CPU load ─────────────────────────────────────────────────────────────────


def get_cpu_load() -> str:
    try:
        per_cpu = psutil.cpu_percent(interval=0.5, percpu=True)
        if not per_cpu:
            return UNKNOWN_VALUE
        avg = sum(per_cpu) / len(per_cpu)
        return f'avg[{avg:.1f}%] max[{max(per_cpu):.1f}%]'
    except Exception:
        return UNKNOWN_VALUE


# ─── Memory usage ─────────────────────────────────────────────────────────────


def get_memory() -> str:
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return ' '.join(
        [
            f'RAM[{fmt_gib(ram.total - ram.available)}/{fmt_gib(ram.total, precision=1)}]',
            f'Swp[{fmt_gib(swap.used)}/{fmt_gib(swap.total, precision=1)}]',
        ]
    )


# ─── Public handler ───────────────────────────────────────────────────────────


@register(REGISTRY, 'hardware')
async def get_hardware_status(config: dict) -> str:
    temp_parts: list[str] = [
        f'cpu[{get_cpu_temp()}]',
        f'ram[{get_ram_temp()}]',
    ]

    for disk_name, disk_temp in await get_disk_temps():
        temp_parts.append(f'{disk_name}[{disk_temp}]')

    lines = [
        'Temp: ' + ' '.join(temp_parts),
        'CPU: ' + get_cpu_load(),
        get_memory(),
    ]
    return '\n'.join(lines)
