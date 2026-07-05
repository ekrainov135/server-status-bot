from __future__ import annotations

import asyncio
import logging
import re
import socket
from urllib.parse import urlparse

import aiohttp
import psutil
from aiohttp import ClientConnectorError

from . import REGISTRY
from .utils import UNKNOWN_VALUE, get_os_name, register

logger = logging.getLogger(__name__)


async def _ping_one(
    host: str,
    count: int = 3,
    timeout: float = 1.0,
) -> float | None:
    if '://' in host:
        parsed = urlparse(host)
        hostname = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    else:
        hostname = host
        port = 443

    if not hostname:
        return None

    loop = asyncio.get_running_loop()

    for _ in range(count):
        try:
            start = loop.time()
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(hostname, port),
                timeout=timeout,
            )
            latency_ms = (loop.time() - start) * 1000

            writer.close()
            await writer.wait_closed()

            return latency_ms

        except Exception:
            continue
    return None


async def _ping_all(
    hosts: list[str],
    count: int,
    timeout: float,
) -> list[float | None]:
    tasks = [_ping_one(h, count, timeout) for h in hosts]
    return list(await asyncio.gather(*tasks))


def _summarize_pings(results: list[float | None]) -> tuple[str, str]:
    total = len(results)
    alive = 0
    avg_rtts: list[float] = []
    max_rtts: float = -1.0

    for r in results:
        if r is not None:
            alive += 1
            avg_rtts.append(r)
            max_rtts = max(max_rtts, r)

    success = f'{alive}/{total}'

    if avg_rtts:
        latency = f'avg[{sum(avg_rtts) / len(avg_rtts):.1f}ms] max[{max_rtts:.1f}ms]'
    else:
        latency = UNKNOWN_VALUE

    return success, latency


def _format_link_speed(speed_mbps: int) -> str | None:
    if speed_mbps <= 0:
        return None

    if speed_mbps >= 1000:
        value = speed_mbps / 1000
        if value.is_integer():
            return f'{int(value)}G'
        return f'{value:g}G'

    return f'{speed_mbps}M'


def _get_link_speed(interface: str) -> str | None:
    stats = psutil.net_if_stats().get(interface)

    if not stats:
        return None

    return _format_link_speed(stats.speed)


async def _get_default_interface_linux(config: dict) -> str | None:
    cmd = config['sh']['get_default_interface_linux'].split()
    proc = await asyncio.create_subprocess_exec(
        cmd[0],
        *cmd[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        return None

    match = re.search(r'\bdev\s+(\S+)', stdout.decode())

    return match.group(1) if match else None


async def _get_default_interface_macos(config: dict) -> str | None:
    cmd = config['sh']['get_default_interface_macos'].split()
    proc = await asyncio.create_subprocess_exec(
        cmd[0],
        *cmd[1:],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )

    stdout, _ = await proc.communicate()

    if proc.returncode != 0:
        return None

    match = re.search(r'interface:\s*(\S+)', stdout.decode())

    return match.group(1) if match else None


async def _get_external_ip() -> str:
    async with (
        aiohttp.ClientSession() as session,
        session.get(
            'https://api.ipify.org',
            timeout=aiohttp.ClientTimeout(total=5),
        ) as response,
    ):
        try:
            response.raise_for_status()
        except ClientConnectorError:
            logger.warning('Failed to fetch external IP')
            return UNKNOWN_VALUE
        return await response.text()


def _get_lan_ip(interface):
    addresses = psutil.net_if_addrs().get(interface)

    if not addresses:
        return None

    for addr in addresses:
        if addr.family == socket.AF_INET:
            return addr.address

    return None


async def get_wan_summary(config: dict) -> dict[str, str | None]:
    """Collect external IP, default interface, link speed and LAN IP.

    Returns an empty dict on unsupported operating systems. Interface-
    related keys are only present when a default interface could be
    detected.
    """

    os_name = get_os_name()
    result: dict[str, str | None] = {}

    if os_name == 'linux':
        interface = await _get_default_interface_linux(config)
    elif os_name == 'macos':
        interface = await _get_default_interface_macos(config)
    else:
        return {}

    result['ip'] = await _get_external_ip()

    if interface:
        result.update(
            {
                'interface': interface,
                'speed': _get_link_speed(interface),
                'lan': _get_lan_ip(interface),
            }
        )
    else:
        logger.warning('Could not determine default network interface')

    return result


# ─── Public handler ───────────────────────────────────────────────────────────


@register(REGISTRY, 'network')
async def get_network_status(config: dict) -> str:
    cfg = config.get('network', {})
    ping_hosts: list[str] = cfg.get('ping_hosts', [])
    dns_servers: list[str] = cfg.get('dns_servers', [])
    count: int = int(cfg.get('ping_count', 3))
    timeout: float = float(cfg.get('ping_timeout', 1.5))

    ping_res, dns_res, wan_summary = await asyncio.gather(
        _ping_all(ping_hosts, count, timeout),
        _ping_all(dns_servers, count, timeout),
        get_wan_summary(config),
    )

    # ── Ping line ──
    if ping_hosts:
        p_ok, p_lat = _summarize_pings(ping_res)
        ping_line = f'Ping: {p_ok} {p_lat}'
    else:
        ping_line = 'Ping: —'

    # ── DNS line ──
    if dns_servers:
        dns_alive = sum(1 for r in dns_res if r is not None)
        dns_line = f'DNS: {dns_alive}/{len(dns_servers)}'
    else:
        dns_line = 'DNS: —'

    wan_summary_line = 'WAN: {interface}[{speed}]'.format(
        interface=wan_summary.get('interface'), speed=wan_summary.get('speed') or UNKNOWN_VALUE
    )
    ip_external_line = 'IP: {}'.format(wan_summary['ip'])
    ip_lan_line = 'LAN: {}'.format(wan_summary.get('lan') or UNKNOWN_VALUE)

    return '\n'.join([ping_line, dns_line, wan_summary_line, ip_external_line, ip_lan_line])
