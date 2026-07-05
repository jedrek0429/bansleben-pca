"""Sitemap, robots.txt, and manifest rendering."""

from __future__ import annotations

import html
import json

from constants import DEFAULT_SITE_NAME, DEFAULT_SITE_SHORT_NAME, DEFAULT_THEME_COLOR
from localization import value_from_locales
from seo import absolute_page_url, page_hreflang, page_lastmod, site_base_url
from urls import asset_url, enabled_alternate_langs, is_enabled


def all_enabled_page_keys_for_lang(ctx, lang: str) -> list[str]:
    keys = []
    for page in ctx.pages_config.get("pages", []):
        key = page["key"]
        if is_enabled(page, lang):
            keys.append(key)
    return keys


def render_sitemap_xml(ctx, seo_config: dict, locales, lang: str) -> str:
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">',
    ]
    for key in all_enabled_page_keys_for_lang(ctx, lang):
        canonical = absolute_page_url(ctx, seo_config, locales, lang, key)
        rows.append("  <url>")
        rows.append("    <loc>" + html.escape(canonical) + "</loc>")
        lastmod = page_lastmod(ctx, seo_config, lang, key)
        if lastmod:
            rows.append("    <lastmod>" + html.escape(lastmod) + "</lastmod>")
        alt_langs = enabled_alternate_langs(ctx, locales, key)
        for alt_lang in alt_langs:
            alt_url = absolute_page_url(ctx, seo_config, locales, alt_lang, key)
            hreflang = page_hreflang(seo_config, alt_lang)
            rows.append(
                '    <xhtml:link rel="alternate" hreflang="'
                + html.escape(hreflang)
                + '" href="'
                + html.escape(alt_url)
                + '" />'
            )
        x_default_lang = seo_config.get("x_default") or "en"
        if x_default_lang in alt_langs:
            x_default_url = absolute_page_url(ctx, seo_config, locales, x_default_lang, key)
            rows.append(
                '    <xhtml:link rel="alternate" hreflang="x-default" href="'
                + html.escape(x_default_url)
                + '" />'
            )
        rows.append("  </url>")
    rows.append("</urlset>")
    return "\n".join(rows) + "\n"


def lang_output_dir(ctx, lang: str):
    lang_root = ctx.dist / lang
    lang_root.mkdir(parents=True, exist_ok=True)
    return lang_root


def write_extra_seo_files(ctx, seo_config: dict, locales, lang: str, lang_root) -> None:
    base = site_base_url(ctx, seo_config, lang, locales)
    (lang_root / "sitemap.xml").write_text(render_sitemap_xml(ctx, seo_config, locales, lang), encoding="utf-8")
    robots = "User-agent: *\nAllow: /\n\nSitemap: " + base + "/sitemap.xml\n"
    (lang_root / "robots.txt").write_text(robots, encoding="utf-8")
    site_name = value_from_locales(lang, "site_name", locales) or DEFAULT_SITE_NAME
    manifest = {
        "name": site_name,
        "short_name": site_name or DEFAULT_SITE_SHORT_NAME,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": seo_config.get("theme_color") or DEFAULT_THEME_COLOR,
        "icons": [{"src": asset_url(ctx, "apple-touch-icon.png"), "sizes": "180x180", "type": "image/png"}],
    }
    (lang_root / "site.webmanifest").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
