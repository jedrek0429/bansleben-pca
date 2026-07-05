"""Page output rendering."""

from __future__ import annotations

import html

from assets import find_images_to_preload, render_preload
from cards import card_group_for, render_card_grid
from localization import value_from_locales
from seo import absolute_page_url, render_404_head, render_seo_head
from template_engine import read_content, render_partial, render_text
from urls import asset_url, is_enabled, page_data, page_prefix, page_slug, page_url


def output_path(ctx, locales, lang: str, key: str):
    slug = page_slug(ctx, locales, lang, key)
    if not slug:
        return ctx.dist / lang / "index.html"
    return ctx.dist / lang / slug / "index.html"


def template_name_for(page: dict, has_cards: bool) -> str:
    key = page.get("key", "")
    requested = page.get("template", "content")
    aliases = {
        "home_cards": "home",
        "standard": "content",
        "content_page": "content",
        "cards_page": "cards",
        "contact_page": "contact",
        "not_found": "404",
    }
    requested = aliases.get(requested, requested)
    if key == "introduction":
        return "home"
    if key == "contact":
        return "contact"
    if requested in {"cards", "cards_with_intro"}:
        return requested
    if has_cards:
        return "cards_with_intro"
    return requested or "content"


def cache_css_link(page: dict, template_name: str) -> str:
    return ""


def hero_style_for_page(ctx, lang: str, locales, key: str) -> str:
    configured = ctx.hero_images.get(key)
    src = configured.get(lang) if isinstance(configured, dict) else configured
    if not src:
        src = value_from_locales(lang, f"hero_images.{key}", locales)
    if not src:
        src = value_from_locales(lang, f"pages.{key}.hero_image", locales)
    if not src:
        src = value_from_locales(lang, f"card_items.{key}.image_src", locales)
    if not src:
        return ""
    src = html.escape(asset_url(ctx, str(src)), quote=True)
    return f' style="background-image: url({src}) !important;"'


def wants_title(page: dict, template_name: str) -> bool:
    if page.get("key") == "introduction":
        return False
    if template_name == "home":
        return False
    return page.get("title", True) is not False


def render_localized_page(ctx, locales, lang: str, page: dict, templates) -> None:
    if not is_enabled(page, lang):
        return

    key = page["key"]
    content_html = read_content(ctx, lang, key)
    card_keys = card_group_for(ctx, locales, key, lang)
    template_name = template_name_for(page, bool(card_keys))
    meta = page_data(ctx, locales, lang, key)

    page_ctx = {
        **meta,
        "url": page_url(ctx, locales, lang, key),
        "canonical_url": absolute_page_url(ctx, ctx.seo_config, locales, lang, key),
        "seo_head": render_seo_head(ctx, ctx.seo_config, locales, lang, key, meta["title"]),
        "content": content_html,
        "cards": render_card_grid(ctx, locales, key, lang, templates),
        "cache_css": cache_css_link(page, template_name),
        "hero_style": hero_style_for_page(ctx, lang, locales, key),
        "hero_class": "",
        "title_section": "",
        "main": "",
        "body": "",
    }

    state = {"page": page_ctx, "content": "", "cards": page_ctx["cards"]}
    if wants_title(page, template_name):
        page_ctx["title_section"] = render_partial(ctx, "title_section", lang, locales, state, templates)

    pieces = []
    if template_name == "home":
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])
    elif template_name == "contact":
        pieces.append(render_partial(ctx, "contact_form", lang, locales, state, templates))
    elif template_name == "cards":
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])
    elif template_name == "cards_with_intro":
        if content_html.strip():
            pieces.append(render_partial(ctx, "introduction", lang, locales, state, templates))
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])
    else:
        pieces.append(render_partial(ctx, "article", lang, locales, state, templates))

    page_ctx["main"] = "\n".join(piece for piece in pieces if piece.strip())
    state["content"] = page_ctx["main"]
    page_ctx["body"] = render_text(ctx, templates["page"], lang, locales, state, templates)
    state["content"] = page_ctx["body"]
    full = render_text(ctx, templates["base"], lang, locales, state, templates)
    preload_html = render_preload(find_images_to_preload(full))
    full = full.replace("</head>", preload_html + "\n</head>")

    dst = output_path(ctx, locales, lang, key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(full, encoding="utf-8")


def render_404(ctx, lang: str, locales, templates) -> None:
    title = value_from_locales(lang, "not_found.title", locales) or "404"
    message = value_from_locales(lang, "not_found.text", locales) or "Page not found."
    back_label = value_from_locales(lang, "not_found.button", locales) or "Back to introduction"
    page_ctx = {
        "key": "404",
        "title": str(title),
        "slug": "404",
        "url": page_prefix(ctx, lang) + "/404.html",
        "canonical_url": "",
        "seo_head": render_404_head(ctx, ctx.seo_config, lang),
        "content": "<p>" + html.escape(str(message)) + "</p>",
        "message": html.escape(str(message)),
        "back_url": html.escape(page_url(ctx, locales, lang, "introduction"), quote=True),
        "back_label": html.escape(str(back_label)),
        "cards": "",
        "cache_css": "",
        "hero_style": "",
        "hero_class": "pca-not-found",
        "title_section": "",
        "main": "",
        "body": "",
    }
    state = {"page": page_ctx, "content": "", "cards": ""}
    page_ctx["title_section"] = render_partial(ctx, "title_section", lang, locales, state, templates)
    page_ctx["main"] = render_partial(ctx, "not_found", lang, locales, state, templates)
    state["content"] = page_ctx["main"]
    page_ctx["body"] = render_text(ctx, templates["page"], lang, locales, state, templates)
    state["content"] = page_ctx["body"]
    full = render_text(ctx, templates["base"], lang, locales, state, templates)
    dst = ctx.dist / lang / "404.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(full, encoding="utf-8")
