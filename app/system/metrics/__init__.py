from __future__ import annotations

from collections.abc import Callable

"""Registry of monitoring metric functions, keyed by name.

Populated via `@register` in `app.system.metrics.*` modules and
consumed by `app.system.handlers.get_status_summary`.
"""
REGISTRY: dict[str, Callable] = {}
