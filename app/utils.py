from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding='utf-8')) or {}


def merge_with_concat(
    common: dict[str, str],
    locale: dict[str, str],
) -> dict[str, str]:
    """Merge shared and locale-specific UI strings.

    Keys present in both dicts are concatenated as "common locale"
    (e.g. an emoji prefix plus the translated label). Keys present in
    only one dict are kept as-is.
    """

    return {
        key: (
            f'{common[key]} {locale[key]}'
            if key in common and key in locale
            else common[key]
            if key in common
            else locale[key]
        )
        for key in common.keys() | locale.keys()
    }
