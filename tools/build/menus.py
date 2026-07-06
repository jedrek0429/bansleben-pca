"""Navigation and language switcher rendering."""

from __future__ import annotations

import html

from constants import DEFAULT_LEGAL_PRACTICE_URL, DEFAULT_MENU_KEYS
from localization import value_from_locales
from urls import is_enabled, page_config, page_title, page_url


def menu_keys(ctx) -> list[str]:
    keys = ctx.pages_config.get("top_menu")
    if isinstance(keys, list) and keys:
        return keys
    return list(DEFAULT_MENU_KEYS)


def menu_label(ctx, locales, lang: str, key: str) -> str:
    value = value_from_locales(lang, f"menu.{key}", locales)
    if value:
        return str(value)
    return page_title(ctx, locales, lang, key)


def render_menu_items(ctx, locales, lang: str, current_key: str, mobile: bool = False) -> str:
    items = []
    for key in menu_keys(ctx):
        page = page_config(ctx, key)
        if page and not is_enabled(page, lang):
            continue
        classes = ["nav-item"]
        if key == "introduction":
            classes.append("nav-item--home")
        if key == current_key:
            classes.append("is-current")
        if mobile and not items:
            classes.append("nav-item--first-mobile")
        aria = ' aria-current="page"' if key == current_key else ""
        href = page_url(ctx, locales, lang, key)
        label = html.escape(menu_label(ctx, locales, lang, key))
        class_attr = " ".join(classes)
        items.append(f'<li class="{class_attr}"><a href="{href}"{aria}>{label}</a></li>')

    external = ctx.pages_config.get("external_links", {}).get("legal_practice", {})
    legal_url = external.get("url") or DEFAULT_LEGAL_PRACTICE_URL
    legal_label = value_from_locales(lang, "menu.legal_practice", locales) or "Legal practice"
    items.append(
        '<li class="nav-item nav-item--external">'
        f'<a href="{html.escape(str(legal_url), quote=True)}">{html.escape(str(legal_label))}</a>'
        '</li>'
    )
    return "\n".join(items)


def render_main_menu(ctx, locales, lang: str, current_key: str) -> str:
    return render_menu_items(ctx, locales, lang, current_key, mobile=False)


def render_mobile_menu(ctx, locales, lang: str, current_key: str) -> str:
    return render_menu_items(ctx, locales, lang, current_key, mobile=True)


def render_language_switcher(ctx, locales, lang: str, key: str) -> str:
    if not ctx.lang_in_url:
        return ""
    links = []
    for code in ctx.langs:
        weight = "font-weight:bold;" if code == lang else ""
        href = page_url(ctx, locales, code, key)
        links.append(f'<a href="{href}" style="margin:0 5px;{weight}">{code.upper()}</a>')
    return '<div class="pca-preview-language-switcher">' + "\n  ".join(links) + "</div>"
