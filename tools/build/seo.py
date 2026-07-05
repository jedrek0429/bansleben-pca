"""SEO head, structured data, and URL metadata rendering."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone

from constants import APPLE_TOUCH_ICON_SIZE, SOCIAL_IMAGE_HEIGHT, SOCIAL_IMAGE_WIDTH
from localization import value_from_locales
from urls import enabled_alternate_langs, page_config, page_title, page_url


def explicit_lastmod(seo_config: dict, lang: str, key: str) -> str:
    lastmod = seo_config.get("lastmod") or {}
    value = lastmod.get(key)
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "").strip()
    return str(value or "").strip()


def file_lastmod_date(path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()


def page_lastmod(ctx, seo_config: dict, lang: str, key: str) -> str:
    configured = explicit_lastmod(seo_config, lang, key)
    if configured:
        return configured
    content_path = ctx.content_path_for(lang, key)
    if content_path:
        return file_lastmod_date(content_path)
    return ""


def site_base_url(ctx, seo_config: dict, lang: str, locales) -> str:
    if not ctx.lang_in_url:
        url = (seo_config.get("site_urls") or {}).get(lang)
        if not url:
            url = value_from_locales(lang, "domain", locales)
        return str(url or "").rstrip("/")
    url = seo_config.get("preview_site_url")
    return str(url or "").rstrip("/")


def absolute_page_url(ctx, seo_config: dict, locales, lang: str, key: str) -> str:
    return site_base_url(ctx, seo_config, lang, locales) + page_url(ctx, locales, lang, key)


def absolute_asset_url(ctx, seo_config: dict, locales, lang: str, path_or_url: str) -> str:
    value = str(path_or_url or "")
    if value.startswith(("http://", "https://")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return site_base_url(ctx, seo_config, lang, locales) + value


def seo_description(seo_config: dict, lang: str, key: str) -> str:
    descriptions = seo_config.get("descriptions") or {}
    page_descriptions = descriptions.get(key) or {}
    value = page_descriptions.get(lang)
    if value:
        return str(value)
    defaults = seo_config.get("default_descriptions") or {}
    return str(defaults.get(lang) or defaults.get("en") or "")


def page_og_locale(seo_config: dict, lang: str) -> str:
    return str((seo_config.get("og_locale") or {}).get(lang) or lang)


def page_hreflang(seo_config: dict, lang: str) -> str:
    return str((seo_config.get("hreflang") or {}).get(lang) or lang)


def json_script(data: dict) -> str:
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "</script>"


def breadcrumb_items(ctx, seo_config: dict, locales, lang: str, key: str) -> list[dict]:
    items = []
    chain = []
    current = page_config(ctx, key)
    while current:
        chain.append(current["key"])
        parent_key = current.get("parent")
        current = page_config(ctx, parent_key) if parent_key else None
    chain.reverse()
    if key != "introduction":
        chain.insert(0, "introduction")

    seen = []
    for item_key in chain:
        if item_key not in seen:
            seen.append(item_key)

    for index, item_key in enumerate(seen, start=1):
        items.append({
            "@type": "ListItem",
            "position": index,
            "name": page_title(ctx, locales, lang, item_key),
            "item": absolute_page_url(ctx, seo_config, locales, lang, item_key),
        })
    return items


def schema_page_type(key: str) -> str:
    return {
        "contact": "ContactPage",
        "who_we_are": "AboutPage",
        "whom_to_contact": "CollectionPage",
    }.get(key, "WebPage")


def organization_url(schema_cfg: dict, site: str, lang: str) -> str:
    url = schema_cfg.get("url")
    if not url:
        return site
    lang_suffixes = schema_cfg.get("url_langs") or {}
    return url + str(lang_suffixes.get(lang, lang))


def organization_address(schema_cfg: dict) -> dict | None:
    address = schema_cfg.get("address") or {}
    required = ["street_address", "address_locality", "address_region", "postal_code", "address_country"]
    if not all(address.get(key) for key in required):
        return None
    return {
        "@type": "PostalAddress",
        "streetAddress": address["street_address"],
        "addressLocality": address["address_locality"],
        "addressRegion": address["address_region"],
        "postalCode": address["postal_code"],
        "addressCountry": address["address_country"],
    }


def render_schema(ctx, seo_config: dict, locales, lang: str, key: str, title: str, description: str, canonical: str) -> str:
    site_name = value_from_locales(lang, "site_name", locales) or title
    logo_src = value_from_locales(lang, "brand.logo_src", locales) or "/assets/favicon.svg"
    schema_cfg = seo_config.get("schema") or {}
    url = organization_url(schema_cfg, site_base_url(ctx, seo_config, lang, locales), lang)

    organization = {
        "@context": "https://schema.org",
        "@type": "LegalService",
        "@id": url + "/#legalservice",
        "name": site_name,
        "legalName": schema_cfg.get("legal_name") or site_name,
        "url": url + "/",
        "logo": absolute_asset_url(ctx, seo_config, locales, lang, logo_src),
        "areaServed": schema_cfg.get("area_served") or "Poland",
        "availableLanguage": schema_cfg.get("languages") or [],
        "sameAs": schema_cfg.get("same_as") or [],
        "telephone": schema_cfg.get("telephone"),
    }
    address = organization_address(schema_cfg)
    if address:
        organization["address"] = address

    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": site_base_url(ctx, seo_config, lang, locales) + "/#website",
        "name": site_name,
        "url": site_base_url(ctx, seo_config, lang, locales) + "/",
        "publisher": {"@id": organization["@id"]},
        "inLanguage": page_hreflang(seo_config, lang),
    }

    webpage = {
        "@context": "https://schema.org",
        "@type": schema_page_type(key),
        "@id": canonical + "#webpage",
        "url": canonical,
        "name": title,
        "description": description,
        "isPartOf": {"@id": website["@id"]},
        "about": {"@id": organization["@id"]},
        "inLanguage": page_hreflang(seo_config, lang),
    }
    if key in {"contact", "who_we_are"}:
        webpage["mainEntity"] = {"@id": organization["@id"]}

    pieces = [json_script(organization), json_script(website), json_script(webpage)]
    crumbs = breadcrumb_items(ctx, seo_config, locales, lang, key)
    if len(crumbs) > 1:
        pieces.append(json_script({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": crumbs,
        }))
    return "\n".join(pieces)


def icon_href(ctx, icons: dict, key: str) -> str:
    from urls import asset_url
    return html.escape(asset_url(ctx, icons[key]), quote=True)


def render_icons(ctx, seo_config: dict, lang: str) -> list[str]:
    lines = []
    icons = seo_config.get("icons") or {}
    if icons.get("svg"):
        lines.append(f'<link rel="icon" type="image/svg+xml" href="{icon_href(ctx, icons, "svg")}">')
    if icons.get("png_32"):
        lines.append(f'<link rel="icon" type="image/png" sizes="32x32" href="{icon_href(ctx, icons, "png_32")}">')
    if icons.get("png_16"):
        lines.append(f'<link rel="icon" type="image/png" sizes="16x16" href="{icon_href(ctx, icons, "png_16")}">')
    if icons.get("apple_touch"):
        lines.append(f'<link rel="apple-touch-icon" sizes="{APPLE_TOUCH_ICON_SIZE}x{APPLE_TOUCH_ICON_SIZE}" href="{icon_href(ctx, icons, "apple_touch")}">')
    return lines


def render_seo_head(ctx, seo_config: dict, locales, lang: str, key: str, title: str) -> str:
    description = seo_description(seo_config, lang, key)
    canonical = absolute_page_url(ctx, seo_config, locales, lang, key)
    site_name = value_from_locales(lang, "site_name", locales) or ""
    full_title = f"{title} | {site_name}" if site_name else title
    social_image = (seo_config.get("social_images") or {}).get(lang) or ""
    social_image_abs = absolute_asset_url(ctx, seo_config, locales, lang, social_image) if social_image else ""

    lines = []
    if description:
        lines.append(f'<meta name="description" content="{html.escape(description, quote=True)}">')
    lines.append(f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">')

    alternate_langs = enabled_alternate_langs(ctx, locales, key)
    for alt_lang in alternate_langs:
        alt_url = absolute_page_url(ctx, seo_config, locales, alt_lang, key)
        hreflang = page_hreflang(seo_config, alt_lang)
        lines.append(f'<link rel="alternate" hreflang="{html.escape(hreflang, quote=True)}" href="{html.escape(alt_url, quote=True)}">')

    x_default_lang = seo_config.get("x_default") or "en"
    if x_default_lang in alternate_langs:
        x_default_url = absolute_page_url(ctx, seo_config, locales, x_default_lang, key)
        lines.append(f'<link rel="alternate" hreflang="x-default" href="{html.escape(x_default_url, quote=True)}">')

    lines.extend(render_icons(ctx, seo_config, lang))
    if seo_config.get("theme_color"):
        lines.append(f'<meta name="theme-color" content="{html.escape(str(seo_config["theme_color"]), quote=True)}">')

    lines.extend([
        f'<meta property="og:site_name" content="{html.escape(str(site_name), quote=True)}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:title" content="{html.escape(full_title, quote=True)}">',
        f'<meta property="og:description" content="{html.escape(description, quote=True)}">',
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">',
        f'<meta property="og:locale" content="{html.escape(page_og_locale(seo_config, lang), quote=True)}">',
    ])

    for alt_lang in alternate_langs:
        if alt_lang != lang:
            lines.append(f'<meta property="og:locale:alternate" content="{html.escape(page_og_locale(seo_config, alt_lang), quote=True)}">')

    if social_image_abs:
        lines.extend([
            f'<meta property="og:image" content="{html.escape(social_image_abs, quote=True)}">',
            f'<meta property="og:image:width" content="{SOCIAL_IMAGE_WIDTH}">',
            f'<meta property="og:image:height" content="{SOCIAL_IMAGE_HEIGHT}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{html.escape(full_title, quote=True)}">',
            f'<meta name="twitter:description" content="{html.escape(description, quote=True)}">',
            f'<meta name="twitter:image" content="{html.escape(social_image_abs, quote=True)}">',
        ])

    lines.append(render_schema(ctx, seo_config, locales, lang, key, title, description, canonical))
    return "\n".join(lines)


def render_404_head(ctx, seo_config: dict, lang: str) -> str:
    lines = [
        '<meta name="robots" content="noindex,follow">',
        '<meta name="description" content="Page not found.">',
    ]
    lines.extend(render_icons(ctx, seo_config, lang))
    if seo_config.get("theme_color"):
        lines.append(f'<meta name="theme-color" content="{html.escape(str(seo_config["theme_color"]), quote=True)}">')
    return "\n".join(lines)
