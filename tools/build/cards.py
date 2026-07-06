"""Card group and card-grid rendering."""

from __future__ import annotations

import html

from assets import primary_variant_url, responsive_image_srcset
from localization import value_from_locales
from template_engine import render_text
from urls import asset_url, is_enabled, page_config, page_slug, page_title, page_url


def card_group_for(ctx, locales, page_key: str, lang: str) -> list[str]:
    """Resolve card keys assigned to a page and filter disabled or unsluggable pages."""
    cards = None

    if isinstance(ctx.cards_config, dict):
        cards = ctx.cards_config.get(page_key)

    if cards is None:
        cards = ctx.pages_config.get("card_groups", {}).get(page_key)

    if isinstance(cards, dict):
        cards = cards.get(lang) or cards.get("en") or []

    if not isinstance(cards, list):
        cards = []

    keys = list(cards)
    if page_key == "introduction" and "the_hague_convention" not in keys:
        keys.append("the_hague_convention")

    filtered = []
    for key in keys:
        page = page_config(ctx, key)
        if page and not is_enabled(page, lang):
            continue
        if page and not page_slug(ctx, locales, lang, key):
            continue
        filtered.append(key)

    return filtered


def card_image_sizes(cols: int) -> str:
    if cols == 1:
        return "(max-width: 560px) calc(100vw - 26px), (max-width: 900px) calc(100vw - 40px), 1080px"
    if cols == 2:
        return "(max-width: 560px) calc(100vw - 26px), (max-width: 900px) calc(100vw - 40px), (max-width: 1080px) calc((100vw - 74px) / 2), 523px"
    return "(max-width: 560px) calc(100vw - 26px), (max-width: 900px) calc(100vw - 40px), (max-width: 1080px) calc((100vw - 108px) / 3), 337px"


def render_card(ctx, locales, lang: str, key: str, col_index: int, cols: int, card_index: int, templates) -> str:
    """Render one card item with localized title, image metadata, URL, layout width, and read-more label."""
    title = value_from_locales(lang, f"card_items.{key}.title", locales) or page_title(ctx, locales, lang, key)
    img_src_value = value_from_locales(lang, f"card_items.{key}.image_src", locales) or ""
    fallback_src = asset_url(ctx, str(img_src_value)) if img_src_value else ""
    img_alt = value_from_locales(lang, f"card_items.{key}.image_alt", locales) or ""
    img_title = value_from_locales(lang, f"card_items.{key}.image_title", locales) or img_alt
    read_more = value_from_locales(lang, "common.read_more", locales) or "READ MORE"
    href = page_url(ctx, locales, lang, key)
    is_leading_card = card_index == 0

    width_class = {
        1: "pca-card--full",
        2: "pca-card--half",
        3: "pca-card--third",
    }.get(cols, "pca-card--third")

    image_info = ctx.image_info(str(img_src_value))
    image_src = primary_variant_url(ctx, str(img_src_value), ".webp") if img_src_value else ""
    src = html.escape(str(image_src), quote=True)
    responsive_srcset = responsive_image_srcset(ctx, str(img_src_value), ".webp") if img_src_value else ""
    sizes = card_image_sizes(cols)
    srcset = ""
    if responsive_srcset:
        srcset = f'srcset="{html.escape(responsive_srcset, quote=True)}" sizes="{html.escape(sizes, quote=True)}"'

    render_state = {
        "card": {
            "width_class": width_class,
            "last": "",
            "image_src": src,
            "fallback_src": html.escape(str(fallback_src), quote=True),
            "image_alt": html.escape(str(img_alt), quote=True),
            "image_title": html.escape(str(img_title)),
            "image_width": html.escape(str(image_info.get("width", "")), quote=True),
            "image_height": html.escape(str(image_info.get("height", "")), quote=True),
            "srcset": srcset,
            "fetchpriority": "high" if is_leading_card else "auto",
            "loading": "eager" if is_leading_card else "lazy",
            "title": html.escape(str(title)),
            "href": href,
            "read_more": html.escape(str(read_more)),
        }
    }

    return render_text(ctx, templates["partials"]["card"], lang, locales, render_state, templates)


def chunk_cards(keys: list[str]) -> list[list[str]]:
    """Split card keys into rows preserving the intended 2-column or 3-column layout."""
    rows = []
    i = 0
    while i < len(keys):
        remaining = len(keys) - i
        if remaining == 4:
            size = 2
        elif remaining == 2:
            size = 2
        else:
            size = min(3, remaining)
        rows.append(keys[i:i + size])
        i += size
    return rows


def render_card_grid(ctx, locales, page_key: str, lang: str, templates) -> str:
    """Render the full card section for a page."""
    keys = card_group_for(ctx, locales, page_key, lang)
    if not keys:
        return ""

    rendered_rows = []
    card_index = 0
    for row_keys in chunk_cards(keys):
        cols = len(row_keys)
        rendered_cards = []
        for col_index, key in enumerate(row_keys):
            rendered_cards.append(render_card(ctx, locales, lang, key, col_index, cols, card_index, templates))
            card_index += 1
        row_state = {"row": {"cards": "\n".join(rendered_cards)}}
        rendered_rows.append(
            render_text(ctx, templates["partials"]["card_row"], lang, locales, row_state, templates)
        )

    section_state = {
        "section": {
            "id": 0 if page_key == "introduction" else 1,
            "rows": "\n".join(rendered_rows),
        }
    }
    return render_text(ctx, templates["partials"]["card_section"], lang, locales, section_state, templates)
