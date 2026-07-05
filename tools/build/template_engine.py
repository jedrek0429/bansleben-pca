"""Template loading and token rendering."""

from __future__ import annotations

import json
import re

from common import display_path
from images import resolve_images
from localization import nested_get, value_from_locales
from menus import render_language_switcher, render_main_menu, render_mobile_menu
from renderer import markdown_to_html
from urls import asset_url, page_url

TOKEN_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")
TEMPLATE_RECURSION_LIMIT = 12


def load_templates(ctx) -> dict:
    """Load base/page templates and required template fragment directories."""
    template_dir = ctx.root / "templates"
    templates = {"partials": {}, "css": {}}

    for name in ["base", "page"]:
        path = template_dir / f"{name}.html"
        if not path.exists():
            raise SystemExit(f"Missing template: {display_path(path, ctx.root)}")
        templates[name] = path.read_text(encoding="utf-8")

    for group, dirname, pattern in [
        ("partials", "partials", "*.html"),
        ("css", "css", "*.css"),
    ]:
        fragment_dir = template_dir / dirname
        if not fragment_dir.exists():
            raise SystemExit(f"Missing template dir: {display_path(fragment_dir, ctx.root)}")
        for path in sorted(fragment_dir.glob(pattern)):
            templates[group][path.stem] = path.read_text(encoding="utf-8")

    return templates


def read_content(ctx, lang: str, key: str) -> str:
    """Load Markdown content and resolve image URLs for the current output mode."""
    markdown = ctx.read_markdown(lang, key)
    if not markdown:
        return ""
    markdown = resolve_images(markdown, ctx, lang)
    return markdown_to_html(markdown, ctx.url_prefix)


def render_text(ctx, text: str, lang: str, locales, render_state=None, templates=None, depth: int = 0) -> str:
    """Replace template tokens with values from context, partials, content files, and locales."""
    if depth > TEMPLATE_RECURSION_LIMIT:
        return text

    render_state = render_state or {}
    templates = templates or {"partials": {}, "css": {}}
    page = render_state.get("page", {})

    def unresolved(token: str) -> str:
        return "{{" + token + "}}"

    def context_value(source: dict, key: str) -> str:
        value = nested_get(source, key)
        return "" if value is None else str(value)

    def template_value(group: str, name: str, token: str) -> str:
        value = templates.get(group, {}).get(name)
        return unresolved(token) if value is None else value

    def brand_value(name: str, token: str) -> str:
        logo_src = value_from_locales(lang, "brand.logo_src", locales) or ""
        if name == "logo_src":
            return asset_url(ctx, str(logo_src))
        image_info = ctx.image_info(str(logo_src))
        if name == "logo_width":
            return str(image_info.get("width", ""))
        if name == "logo_height":
            return str(image_info.get("height", ""))
        if name == "logo_webp_src":
            return asset_url(ctx, str(image_info.get("webp_src", "")))
        value = value_from_locales(lang, token, locales)
        return unresolved(token) if value is None else str(value)

    direct_tokens = {
        "lang": lambda: lang,
        "url_prefix": lambda: ctx.url_prefix,
        "home_url": lambda: page_url(ctx, locales, lang, "introduction"),
        "contact_action": lambda: asset_url(ctx, "contact.php"),
        "content": lambda: str(render_state.get("content") or page.get("body") or page.get("main") or ""),
        "cards": lambda: str(render_state.get("cards") or page.get("cards") or ""),
        "language_switcher": lambda: render_language_switcher(ctx, locales, lang, page.get("key", "introduction")),
        "main_menu": lambda: render_main_menu(ctx, locales, lang, page.get("key", "introduction")),
        "mobile_menu": lambda: render_mobile_menu(ctx, locales, lang, page.get("key", "introduction")),
        "privacy_policy_url": lambda: page_url(ctx, locales, lang, "privacy_policy"),
        "common.select_page": lambda: {
            "en": "Select page",
            "fr": "Sélectionner une page",
            "hr": "Odaberite stranicu",
        }.get(lang, "Select page"),
    }

    context_prefixes = {
        "page": page,
        "card": render_state.get("card", {}),
        "row": render_state.get("row", {}),
        "section": render_state.get("section", {}),
    }

    def token_value(match):
        token = match.group(1).strip()

        if token in direct_tokens:
            return direct_tokens[token]()

        if "." in token:
            prefix, name = token.split(".", 1)
            if prefix == "brand":
                return brand_value(name, token)
            if prefix == "partial":
                return template_value("partials", name, token)
            if prefix == "css":
                return template_value("css", name, token)
            if prefix == "content":
                return read_content(ctx, lang, name)
            if prefix in context_prefixes:
                return context_value(context_prefixes[prefix], name)

        value = value_from_locales(lang, token, locales)
        if value is None:
            return unresolved(token)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    rendered = TOKEN_RE.sub(token_value, text)
    if rendered != text and TOKEN_RE.search(rendered):
        return render_text(ctx, rendered, lang, locales, render_state, templates, depth + 1)
    return rendered


def render_partial(ctx, name: str, lang: str, locales, render_state, templates) -> str:
    partial = templates.get("partials", {}).get(name, "")
    if not partial:
        return ""
    return render_text(ctx, partial, lang, locales, render_state, templates)
