"""Page and asset URL helpers.

Shared page structure comes from config/pages.json. Locale files own whether a
page exists in that site and its translated title/slug. Parent paths are always
resolved from the shared page graph so a locale cannot redefine hierarchy.
"""

from __future__ import annotations

from context import BuildContext


def page_config(ctx: BuildContext, key: str, lang: str | None = None) -> dict:
    if lang is not None:
        return ctx.page_config(lang, key)
    shared = ctx.pages_by_key.get(key)
    if shared:
        return shared
    for code in ctx.langs:
        page = ctx.page_config(code, key)
        if page:
            return page
    return {}


def localized_page(locales, lang: str, key: str) -> dict:
    locale = locales.get(lang, {}) if isinstance(locales, dict) else {}
    pages = locale.get("pages", {}) if isinstance(locale, dict) else {}
    entry = pages.get(key, {}) if isinstance(pages, dict) else {}
    return entry if isinstance(entry, dict) else {}


def is_enabled(*args) -> bool:
    if len(args) == 2:
        page, lang = args
        enabled = page.get("enabled") if isinstance(page, dict) else None
        if isinstance(enabled, list):
            return lang in enabled
        return enabled is not False
    if len(args) != 4:
        raise TypeError("is_enabled expects (page, lang) or (ctx, locales, lang, key)")
    ctx, locales, lang, key = args
    if not page_config(ctx, key, lang):
        return False
    entry = localized_page(locales, lang, key)
    if not entry:
        return False
    return entry.get("enabled", True) is not False


def page_title(ctx: BuildContext, locales, lang: str, key: str) -> str:
    title = localized_page(locales, lang, key).get("title")
    if title:
        return str(title)
    return key.replace("_", " ").title()


def _slug_segment(ctx: BuildContext, locales, lang: str, key: str) -> str:
    if key == "introduction":
        return ""
    raw = str(localized_page(locales, lang, key).get("slug") or "").strip("/")
    page = page_config(ctx, key, lang)
    if page.get("parent") and "/" in raw:
        return raw.rsplit("/", 1)[-1]
    return raw


def page_slug(ctx: BuildContext, locales, lang: str, key: str, _seen=None) -> str:
    if key == "introduction":
        return ""
    page = page_config(ctx, key, lang)
    if not page:
        return ""
    seen = set(_seen or ())
    if key in seen:
        raise ValueError(f"Cycle in page hierarchy at '{key}'")
    seen.add(key)
    segment = _slug_segment(ctx, locales, lang, key)
    if not segment:
        return ""
    parent = page.get("parent")
    if not parent:
        return segment
    parent_slug = page_slug(ctx, locales, lang, str(parent), seen)
    if not parent_slug:
        return ""
    return f"{parent_slug}/{segment}"


def page_data(ctx: BuildContext, locales, lang: str, key: str) -> dict:
    return {"key": key, "title": page_title(ctx, locales, lang, key), "slug": page_slug(ctx, locales, lang, key)}


def page_prefix(ctx: BuildContext, lang: str) -> str:
    prefix = ctx.url_prefix
    if ctx.lang_in_url:
        prefix = f"{prefix}/{lang}" if prefix else f"/{lang}"
    return prefix.rstrip("/")


def root_url(ctx: BuildContext, lang: str) -> str:
    return (page_prefix(ctx, lang) or "") + "/"


def asset_url(ctx: BuildContext, path: str) -> str:
    value = str(path or "")
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return f"{ctx.url_prefix}{value}" if ctx.url_prefix else value


def page_url(ctx: BuildContext, locales, lang: str, key: str) -> str:
    if not is_enabled(ctx, locales, lang, key):
        return root_url(ctx, lang)
    slug = page_slug(ctx, locales, lang, key)
    if not slug:
        return root_url(ctx, lang)
    prefix = page_prefix(ctx, lang)
    return f"{prefix}/{slug}/" if prefix else f"/{slug}/"


def enabled_alternate_langs(ctx: BuildContext, locales, key: str) -> list[str]:
    langs = []
    for lang in ctx.langs:
        if not is_enabled(ctx, locales, lang, key):
            continue
        if key == "introduction" or page_slug(ctx, locales, lang, key):
            langs.append(lang)
    return langs
