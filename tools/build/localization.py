"""Localization helpers for the PCA static site builder."""

from __future__ import annotations


def nested_get(data, key: str):
    cur = data
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


def value_from_locales(lang: str, key: str, locales):
    """Return a nested localized value, falling back to English when missing."""
    value = nested_get(locales.get(lang, {}), key)
    if value is None and lang != "en":
        value = nested_get(locales.get("en", {}), key)
    return value
