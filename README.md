# Server status bot

![Python](https://img.shields.io/badge/python-3.14%2B-blue)
[![CI](https://github.com/ekrainov135/server-status-bot/actions/workflows/ci.yaml/badge.svg)](https://github.com/ekrainov135/server-status-bot/actions/workflows/ci.yaml)
[![Ruff](https://img.shields.io/badge/lint-ruff-46a2f1.svg)](https://github.com/astral-sh/ruff)
![GitHub License](https://img.shields.io/github/license/ekrainov135/server-status-bot)

## Description

A Telegram bot for monitoring and managing a home or remote Linux server:
uptime, hardware, and network status, plus start/stop/restart control for a
configurable list of system services and a reboot action.

Beyond its practical use, the project is structured as a reusable template
for aiogram 3.x bots. Navigation, screens, and widgets are declared in
YAML/Jinja2 config rather than hardcoded, and the keyboard/dialog engine
(`lib/aiogram_keyboard`) has no dependency on this bot's domain logic, so it
can be reused as-is in other projects.

## Features

- Obtaining basic server information
- Russian / English interface, switchable per chat
- Admin-only access via a Telegram user ID allowlist
- Screens, buttons, and navigation defined declaratively in config files,
  not in Python code

## Requirements

- Python 3.14+
- Linux, `systemd`-based (primary target). Network interface detection has
  partial macOS support; other monitoring and all service-management
  features assume `systemctl`.
- A Telegram bot token
- Optional: `smartmontools` (`smartctl`) for disk temperature reporting —
  degrades gracefully if absent
- Dependencies (see `pyproject.toml`): `aiogram`, `psutil`, `pydantic`,
  `PyYAML`, `Jinja2`, `python-dotenv`

## Installation

```bash
git clone <repo-url>
cd server-status-bot
pip install --upgrade pip
pip install -e .
```

For development (linting, type checking, tests):

```bash
pip install -e ".[dev]"
```

## Configuration

Configuration is split between environment variables and YAML files.

**`.env`** (create in the project root):

```
BOT_TOKEN=<telegram bot token>
ADMINS=<comma-separated Telegram user IDs>
```

Only users listed in `ADMINS` can use the bot; everyone else is silently
ignored.

**`app/settings.py`** — `SERVICE_LIST` defines which system services are
offered for management. At startup, only the ones actually present on the
host (`command -v <name>`) get a screen.

**`app/system/config.yaml`** — ping targets, DNS servers used for network
checks, and the shell command templates used for service management,
reboot, and interface detection.

**`data/bot/configs/*.yaml.j2`** — navigation graph (`nav.yaml.j2`), widget
definitions (`widgets.yaml.j2`), and screen headers (`header.yaml.j2`).
This is the main place to add or change screens and buttons.

**`data/bot/strings/*.yaml`** — UI text per locale (`ru.yaml`, `en.yaml`)
plus `common.yaml` for locale-independent strings (icons, symbols) that get
merged with each locale's text.

## Running

```bash
python run.py
```

The bot uses long polling; no webhook or public endpoint is required.

## Project structure

```
app/
  bot/            Telegram-specific logic: handlers, widgets, access
                  middleware, and the config-driven screen registry
  system/         Monitoring and service management, independent of
                  Telegram/aiogram
  settings.py     Environment and locale loading
lib/
  aiogram_keyboard/  Reusable navigation/widget/dialog engine, no
                     dependency on app/*
data/
  bot/configs/    Jinja2/YAML screen and widget declarations
  bot/strings/    Locale string tables
tests/            Unit tests, mirroring the app/lib layout
run.py            Entry point
```

## Architecture

- **Config-driven navigation.** Screens, their buttons, and headers are
  declared in `data/bot/configs/*.yaml.j2` and rendered with Jinja2 (e.g.
  one row per detected service). Adding a screen or button normally does
  not require touching Python.
- **Widget dispatch by convention.** Each widget declares its buttons via
  `_build_specs`; pressing a button with action `foo` calls `on_foo` on the
  widget. New interactive behavior is added by defining a widget subclass
  and its `on_<action>` methods — this is the main extension point.
- **Registries for commands and metrics.** `SYSTEM_HANDLERS` and the
  metrics `REGISTRY` map string names (referenced from config) to Python
  functions via a `@register` decorator, so new commands or monitoring
  checks are plugged in without modifying the dispatch code.
- **Library / application boundary.** `lib/aiogram_keyboard` implements
  dialog state, keyboard rendering, and widget dispatch as a standalone
  engine; `app/*` supplies the domain-specific widgets, config, and system
  calls. This boundary is what makes the engine reusable in other bots.
- **Dialog state** is stored via aiogram's FSM (`MemoryStorage` by
  default) and is only used to track navigation breadcrumbs and per-widget
  data — no business data is persisted.

## Limitations


- **Platform.** Built for Linux with `systemd`. Service management,
  reboot, and hardware sensor readouts rely on `systemctl` and `psutil`'s
  Linux-specific sensor APIs, neither of which exists elsewhere. Network
  interface detection has a macOS code path, but running on non-Linux or
  non-systemd hosts would require changing the shell commands in
  `app/system/config.yaml` — it's not a configuration toggle.
- **Single process, single event loop.** The bot runs as one asyncio
  process with no multi-threading or multi-processing; every monitoring
  check is a short-lived subprocess spawned from that loop. This fits a
  handful of admins polling one host, not high-concurrency use.
