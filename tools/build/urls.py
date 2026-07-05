"""Page and asset URL helpers."""

from __future__ import annotations

from context import BuildContext
from localization import value_from_locales


def page_config(ctx: BuildContext, key: str) -> dict:
    return ctx.pages_by_key.get(key, {})


def is_enabled(page: dict, lang: str) -> bool:
    enabled = page.get("enabled")
    if not enabled:
        return True
    return lang in enabled


def page_title(ctx: BuildContext, locales, lang: str, key: str) -> str:
    page = page_config(ctx, key)
    title = (page.get("titles") or {}).get(lang)
    if title:
        return str(title)

    title = value_from_locales(lang, f"pages.{key}.title", locales)
    if title:
        return str(title)

    return key.replace("_", " ").title()


def page_slug(ctx: BuildContext, locales, lang: str, key: str) -> str:
    """Resolve the URL slug for a page in a language."""
    page = page_config(ctx, key)
    slug = (page.get("slugs") or {}).get(lang)

    if slug is None:
        loc = value_from_locales(lang, f"pages.{key}.slug", locales)
        slug = loc if loc is not None else key.replace("_", "-")

    slug = str(slug).strip("/")

    if key == "introduction":
        slug = ""

    return slug


def page_data(ctx: BuildContext, locales, lang: str, key: str) -> dict:
    return {
        "key": key,
        "title": page_title(ctx, locales, lang, key),
        "slug": page_slug(ctx, locales, lang, key),
    }


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
    page = page_config(ctx, key)

    if page and not is_enabled(page, lang):
        return root_url(ctx, lang)

    slug = page_slug(ctx, locales, lang, key)

    if not slug:
        return root_url(ctx, lang)

    prefix = page_prefix(ctx, lang)
    return f"{prefix}/{slug}/" if prefix else f"/{slug}/"


def enabled_alternate_langs(ctx: BuildContext, locales, key: str) -> list[str]:
    """Return languages where a page is enabled and should be exposed as alternate URLs."""
    page = page_config(ctx, key)
    if not page:
        return []

    langs = []
    for lang in ctx.langs:
        if not is_enabled(page, lang):
            continue
        if key == "introduction" or page_slug(ctx, locales, lang, key) != "":
            langs.append(lang)
    return langs
