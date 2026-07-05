"""
Clean PCA static site build.

Source of truth:
- config/pages.json: pages, enabled languages, titles, slugs, templates, menu.
- config/cards.json: card groups.
- locales/<lang>.json: labels, card_items, shared blocks.
- content/<lang>/<key>.md: article/intro content.
- templates/base.html, templates/page.html, templates/partials/*.html: layout shell.

Usage: run from site-src root (or pass `--root /path/to/site-src`).
"""

import argparse
import html
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import imagesize

from common import (
    CLR_GREEN,
    CLR_RED,
    CLR_WHITE,
    CLR_YELLOW,
    color,
    display_path,
    load_json,
    load_optional_json,
    print_group,
    print_labeled,
    print_section,
)
from renderer import markdown_to_html


DEFAULT_ROOT = Path(__file__).resolve().parents[1]
ROOT = DEFAULT_ROOT
DIST = ROOT.parent / "site-dist"

TERM_WIDTH = min(shutil.get_terminal_size((120, 20)).columns, 140)

def configure_paths(root) -> None:
    """Set build paths from the selected site-src root."""
    global ROOT, DIST

    ROOT = Path(root).expanduser().resolve()
    DIST = ROOT.parent / "site-dist"

URL_PREFIX = os.environ.get("SITE_URL_PREFIX", "/").strip()
if URL_PREFIX == "/":
    URL_PREFIX = ""
else:
    URL_PREFIX = URL_PREFIX.rstrip("/")

LANG_IN_URL = os.environ.get("SITE_LANG_IN_URL", "0").strip().lower() not in {"0", "false", "no", "off"}
LANGS = ["en", "fr", "hr"]

TOKEN_RE = re.compile(r"{{\s*([^{}]+?)\s*}}")

PAGES_CONFIG = {}
PAGES_BY_KEY = {}
SEO_CONFIG = {}


def load_locale(lang: str):
    return load_json(ROOT / "locales" / f"{lang}.json")



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
    """Return a nested localized value, falling back to English when the requested language is missing."""
    value = nested_get(locales.get(lang, {}), key)
    if value is None and lang != "en":
        value = nested_get(locales.get("en", {}), key)
    return value



def page_config(key: str) -> dict:
    return PAGES_BY_KEY.get(key, {})



def is_enabled(page: dict, lang: str) -> bool:
    enabled = page.get("enabled")
    if not enabled:
        return True
    return lang in enabled



def page_title(lang: str, key: str, locales) -> str:
    page = page_config(key)
    title = (page.get("titles") or {}).get(lang)
    if title:
        return str(title)

    title = value_from_locales(lang, f"pages.{key}.title", locales)
    if title:
        return str(title)

    return key.replace("_", " ").title()



def page_slug(lang: str, key: str, locales) -> str:
    """Resolve the URL slug for a page in a language, using page config first, then locale data, then the page key."""
    page = page_config(key)
    slug = (page.get("slugs") or {}).get(lang)

    if slug is None:
        loc = value_from_locales(lang, f"pages.{key}.slug", locales)
        slug = loc if loc is not None else key.replace("_", "-")

    slug = str(slug).strip("/")

    if key == "introduction":
        slug = ""

    return slug



def page_data(locales, lang: str, key: str) -> dict:
    return {
        "key": key,
        "title": page_title(lang, key, locales),
        "slug": page_slug(lang, key, locales),
    }


def page_prefix(lang: str) -> str:
    prefix = URL_PREFIX
    if LANG_IN_URL:
        prefix = f"{prefix}/{lang}" if prefix else f"/{lang}"
    return prefix.rstrip("/")


def root_url(lang: str) -> str:
    return (page_prefix(lang) or "") + "/"


def asset_url(path: str) -> str:
    value = str(path or "")
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return f"{URL_PREFIX}{value}" if URL_PREFIX else value


def page_url(locales, lang: str, key: str) -> str:
    """Build the public relative URL for a page, respecting disabled pages, language prefixes, and homepage slugs."""
    page = page_config(key)

    if page and not is_enabled(page, lang):
        return root_url(lang)

    slug = page_slug(lang, key, locales)

    if not slug:
        return root_url(lang)

    prefix = page_prefix(lang)
    return f"{prefix}/{slug}/" if prefix else f"/{slug}/"



def load_seo_config() -> dict:
    return load_optional_json(ROOT / "config" / "seo.json")

def explicit_lastmod(seo_config: dict, lang: str, key: str) -> str:
    """Return an explicit lastmod date from seo.json if one is configured."""
    lastmod = seo_config.get("lastmod") or {}
    value = lastmod.get(key)

    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or "").strip()

    return str(value or "").strip()



def content_path_for(lang: str, key: str) -> Path | None:
    """Return the Markdown content path that would be used for a page."""
    candidates = [
        ROOT / "content" / lang / f"{key}.md",
        ROOT / "content" / "en" / f"{key}.md",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None

def file_lastmod_date(path: Path) -> str:
    """Return a YYYY-MM-DD date from a file's modification time."""
    return datetime.fromtimestamp(
        path.stat().st_mtime,
        timezone.utc,
    ).date().isoformat()
    
def page_lastmod(seo_config: dict, lang: str, key: str) -> str:
    """Return the sitemap lastmod date for a page, preferring explicit SEO config over file mtime."""
    configured = explicit_lastmod(seo_config, lang, key)
    if configured:
        return configured

    content_path = content_path_for(lang, key)
    if content_path:
        return file_lastmod_date(content_path)

    return ""


def site_base_url(seo_config: dict, lang: str, locales) -> str:
    """Return the absolute base URL for a language from SEO config or locale domain settings."""
    if not LANG_IN_URL:
        url = (seo_config.get("site_urls") or {}).get(lang)
        if not url:
            url = value_from_locales(lang, "domain", locales)
        return str(url or "").rstrip("/")
    else:
        url = seo_config.get("preview_site_url")
        return str(url or "").rstrip("/")



def absolute_page_url(seo_config: dict, locales, lang: str, key: str) -> str:
    """Build the absolute canonical URL for a localized page."""
    base = site_base_url(seo_config, lang, locales)
    path = page_url(locales, lang, key)
    return base + path



def absolute_asset_url(seo_config: dict, locales, lang: str, path_or_url: str) -> str:
    """Convert an asset path or existing URL into an absolute URL for the current language site."""
    value = str(path_or_url or "")
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if not value.startswith("/"):
        value = "/" + value
    return site_base_url(seo_config, lang, locales) + value



def seo_description(seo_config: dict, lang: str, key: str) -> str:
    """Return the SEO description for a page and language, falling back to the configured default description."""
    descriptions = seo_config.get("descriptions") or {}
    page_descriptions = descriptions.get(key) or {}

    value = page_descriptions.get(lang)
    if value:
        return str(value)

    defaults = seo_config.get("default_descriptions") or {}
    return str(defaults.get(lang) or defaults.get("en") or "")



def enabled_alternate_langs(key: str) -> list[str]:
    """Return the languages where a page is enabled and should be exposed as an alternate localized URL."""
    page = page_config(key)
    if not page:
        return []

    return [
        lang for lang in LANGS
        if is_enabled(page, lang) and page_slug(lang, key, {}) != ""
        or key == "introduction" and is_enabled(page, lang)
    ]



def page_og_locale(seo_config: dict, lang: str) -> str:
    return str((seo_config.get("og_locale") or {}).get(lang) or lang)



def page_hreflang(seo_config: dict, lang: str) -> str:
    return str((seo_config.get("hreflang") or {}).get(lang) or lang)



def json_script(data: dict) -> str:
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        + "</script>"
    )



def breadcrumb_items(seo_config: dict, locales, lang: str, key: str) -> list[dict]:
    """Build Schema.org breadcrumb items by walking the configured parent chain for the current page."""
    items = []
    chain = []

    current = page_config(key)
    while current:
        chain.append(current["key"])
        parent_key = current.get("parent")
        current = page_config(parent_key) if parent_key else None

    chain.reverse()

    # Always add homepage first unless current page is homepage.
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
            "name": page_title(lang, item_key, locales),
            "item": absolute_page_url(seo_config, locales, lang, item_key),
        })

    return items



def schema_page_type(key: str) -> str:
    """Return the most specific Schema.org page type for known page keys."""
    return {
        "contact": "ContactPage",
        "who_we_are": "AboutPage",
        "whom_to_contact": "CollectionPage",
    }.get(key, "WebPage")

def organization_url(schema_cfg: dict, site: str, lang: str) -> str:
    url = schema_cfg.get("url")
    if not url:
        return site
    if lang == "hr":
        return url + "en"
    return url + lang 

def render_schema(seo_config: dict, locales, lang: str, key: str, title: str, description: str, canonical: str) -> str:
    """Render JSON-LD structured data for the organization, website, page, and optional breadcrumbs."""
    site_name = value_from_locales(lang, "site_name", locales) or title
    logo_src = value_from_locales(lang, "brand.logo_src", locales) or "/assets/favicon.svg"
    schema_cfg = seo_config.get("schema") or {}
    
    url = organization_url(schema_cfg, site_base_url(seo_config, lang, locales), lang)
    address = schema_cfg.get("address")
    
    organization = {
        "@context": "https://schema.org",
        "@type": "LegalService",
        "@id": url + "/#legalservice",
        "name": site_name,
        "legalName": schema_cfg.get("legal_name") or site_name,
        "url": url + "/",
        "logo": absolute_asset_url(seo_config, locales, lang, logo_src),
        "areaServed": schema_cfg.get("area_served") or "Poland",
        "availableLanguage": schema_cfg.get("languages") or [],
        "sameAs": schema_cfg.get("same_as") or [],
        "telephone": schema_cfg.get("telephone"),
        "address": {
            "@type": "PostalAddress",
            "streetAddress": address["street_address"],
            "addressLocality": address["address_locality"],
            "addressRegion": address["address_region"],
            "postalCode": address["postal_code"],
            "addressCountry": address["address_country"],
        },
    }

    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "@id": site_base_url(seo_config, lang, locales) + "/#website",
        "name": site_name,
        "url": site_base_url(seo_config, lang, locales) + "/",
        "publisher": {
            "@id": organization["@id"]
        },
        "inLanguage": page_hreflang(seo_config, lang),
    }

    webpage = {
        "@context": "https://schema.org",
        "@type": schema_page_type(key),
        "@id": canonical + "#webpage",
        "url": canonical,
        "name": title,
        "description": description,
        "isPartOf": {
            "@id": website["@id"]
        },
        "about": {
            "@id": organization["@id"]
        },
        "inLanguage": page_hreflang(seo_config, lang),
    }
    
    if key in {"contact", "who_we_are"}:
        webpage["mainEntity"] = {
            "@id": organization["@id"]
        }

    pieces = [
        json_script(organization),
        json_script(website),
        json_script(webpage),
    ]

    crumbs = breadcrumb_items(seo_config, locales, lang, key)
    if len(crumbs) > 1:
        pieces.append(json_script({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": crumbs,
        }))

    return "\n".join(pieces)



def icon_href(icons: dict, lang: str, key: str) -> str:
    return html.escape(asset_url(icons[key]), quote=True)



def render_icons(seo_config: dict, lang: str) -> list[str]:
    lines = []
    icons = seo_config.get("icons") or {}
    if icons.get("svg"):
        lines.append(f'<link rel="icon" type="image/svg+xml" href="{icon_href(icons, lang, "svg")}">')
    if icons.get("png_32"):
        lines.append(f'<link rel="icon" type="image/png" sizes="32x32" href="{icon_href(icons, lang, "png_32")}">')
    if icons.get("png_16"):
        lines.append(f'<link rel="icon" type="image/png" sizes="16x16" href="{icon_href(icons, lang, "png_16")}">')
    if icons.get("apple_touch"):
        lines.append(f'<link rel="apple-touch-icon" sizes="180x180" href="{icon_href(icons, lang, "apple_touch")}">')
    return lines



def render_seo_head(seo_config: dict, locales, lang: str, key: str, title: str) -> str:
    """Render SEO-related head tags, including description, canonical URL, hreflang links, icons, Open Graph, Twitter, and schema data."""
    description = seo_description(seo_config, lang, key)
    canonical = absolute_page_url(seo_config, locales, lang, key)
    site_name = value_from_locales(lang, "site_name", locales) or ""
    full_title = f"{title} | {site_name}" if site_name else title

    social_image = (seo_config.get("social_images") or {}).get(lang) or ""
    social_image_abs = absolute_asset_url(seo_config, locales, lang, social_image) if social_image else ""

    lines = []

    if description:
        lines.append(f'<meta name="description" content="{html.escape(description, quote=True)}">')

    lines.append(f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">')

    alternate_langs = enabled_alternate_langs(key)
    for alt_lang in alternate_langs:
        alt_url = absolute_page_url(seo_config, locales, alt_lang, key)
        hreflang = page_hreflang(seo_config, alt_lang)
        lines.append(
            f'<link rel="alternate" hreflang="{html.escape(hreflang, quote=True)}" href="{html.escape(alt_url, quote=True)}">'
        )

    x_default_lang = seo_config.get("x_default") or "en"
    if x_default_lang in alternate_langs:
        x_default_url = absolute_page_url(seo_config, locales, x_default_lang, key)
        lines.append(f'<link rel="alternate" hreflang="x-default" href="{html.escape(x_default_url, quote=True)}">')

    lines.extend(render_icons(seo_config, lang))

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
            lines.append(
                f'<meta property="og:locale:alternate" content="{html.escape(page_og_locale(seo_config, alt_lang), quote=True)}">'
            )

    if social_image_abs:
        lines.extend([
            f'<meta property="og:image" content="{html.escape(social_image_abs, quote=True)}">',
            '<meta property="og:image:width" content="1200">',
            '<meta property="og:image:height" content="630">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{html.escape(full_title, quote=True)}">',
            f'<meta name="twitter:description" content="{html.escape(description, quote=True)}">',
            f'<meta name="twitter:image" content="{html.escape(social_image_abs, quote=True)}">',
        ])

    lines.append(render_schema(seo_config, locales, lang, key, title, description, canonical))

    return "\n".join(lines)

def output_path(locales, lang: str, key: str) -> Path:
    slug = page_slug(lang, key, locales)

    if not slug:
        return DIST / lang / "index.html"

    return DIST / lang / slug / "index.html"



def read_content(lang: str, key: str) -> str:
    """Load Markdown content for a page, preferring the requested language and falling back to English."""
    candidates = [
        ROOT / "content" / lang / f"{key}.md",
        ROOT / "content" / "en" / f"{key}.md",
    ]

    for path in candidates:
        if path.exists():
            return markdown_to_html(path.read_text(encoding="utf-8"), URL_PREFIX)

    return ""



def load_templates():
    """Load the base/page templates and all partial templates required for rendering the static site."""
    template_dir = ROOT / "templates"
    templates = {"partials": {}}

    for name in ["base", "page"]:
        path = template_dir / f"{name}.html"
        if not path.exists():
            raise SystemExit(f"Missing template: {display_path(path, ROOT)}")
        templates[name] = path.read_text(encoding="utf-8")

    partial_dir = template_dir / "partials"
    if not partial_dir.exists():
        raise SystemExit(f"Missing template dir: {display_path(partial_dir, ROOT)}")

    for path in sorted(partial_dir.glob("*.html")):
        templates["partials"][path.stem] = path.read_text(encoding="utf-8")

    return templates



def template_name_for(page: dict, has_cards: bool) -> str:
    """Choose the rendering template for a page based on its config, page key, and whether it has cards."""
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
    """Return an empty legacy theme CSS slot retained for template compatibility."""
    return ""



def hero_style_for_page(lang: str, locales, key: str) -> str:
    """Resolve the hero background image for a page and return the inline CSS style attribute."""
    hero_images = load_optional_json(ROOT / "config" / "hero_images.json")

    src = (
        (hero_images.get(key) or {}).get(lang) if isinstance(hero_images.get(key), dict) else hero_images.get(key)
    )

    if not src:
        src = value_from_locales(lang, f"hero_images.{key}", locales)

    if not src:
        src = value_from_locales(lang, f"pages.{key}.hero_image", locales)

    if not src:
        src = value_from_locales(lang, f"card_items.{key}.image_src", locales)

    if not src:
        return ""

    src = html.escape(asset_url(str(src)), quote=True)

    return f' style="background-image: url({src}) !important;"'



def menu_keys() -> list[str]:
    keys = PAGES_CONFIG.get("top_menu")
    if isinstance(keys, list) and keys:
        return keys
    return ["introduction", "whom_to_contact", "jurisprudence", "contact", "who_we_are"]



def menu_label(lang: str, locales, key: str) -> str:
    value = value_from_locales(lang, f"menu.{key}", locales)
    if value:
        return str(value)
    return page_title(lang, key, locales)



def render_menu_items(lang: str, locales, current_key: str, mobile: bool = False) -> str:
    """Render desktop or mobile menu items for the active language, marking the current page when applicable."""
    items = []

    for idx, key in enumerate(menu_keys()):
        page = page_config(key)
        if page and not is_enabled(page, lang):
            continue

        active = key == current_key

        classes = ["nav-item"]

        if key == "introduction":
            classes.append("nav-item--home")

        if active:
            classes.append("is-current")

        if mobile and not items:
            classes.append("nav-item--first-mobile")

        aria = ' aria-current="page"' if active else ""
        href = page_url(locales, lang, key)
        label = html.escape(menu_label(lang, locales, key))

        items.append(f'<li class="{" ".join(classes)}"><a href="{href}"{aria}>{label}</a></li>')

    external = PAGES_CONFIG.get("external_links", {}).get("legal_practice", {})
    legal_url = external.get("url") or "https://bansleben.pl/"
    legal_label = value_from_locales(lang, "menu.legal_practice", locales) or "Legal practice"

    items.append(
        '<li class="nav-item nav-item--external">'
        f'<a href="{html.escape(str(legal_url), quote=True)}">{html.escape(str(legal_label))}</a>'
        '</li>'
    )

    return "\n".join(items)



def render_main_menu(lang: str, locales, current_key: str) -> str:
    return render_menu_items(lang, locales, current_key, mobile=False)



def render_mobile_menu(lang: str, locales, current_key: str) -> str:
    return render_menu_items(lang, locales, current_key, mobile=True)



def render_language_switcher(lang: str, locales, key: str) -> str:
    """Render the floating language switcher when language URLs are enabled."""
    if not LANG_IN_URL:
        return ""

    links = []

    for code in LANGS:
        weight = "font-weight:bold;" if code == lang else ""
        href = page_url(locales, code, key)
        links.append(f'<a href="{href}" style="margin:0 5px;{weight}">{code.upper()}</a>')

    return (
        '<div class="v2-language-switcher" style="position:fixed;right:18px;bottom:18px;z-index:99999;background:white;border:1px solid #ddd;border-radius:999px;padding:8px 10px;font-family:Arial,sans-serif;font-size:12px;box-shadow:0 8px 25px rgba(0,0,0,.12);">'
        + "\n  ".join(links)
        + "</div>"
    )



def render_text(text: str, lang: str, locales, ctx=None, templates=None, depth: int = 0) -> str:
    """Replace template tokens with values from context, partials, page data, content files, and locale dictionaries."""
    if depth > 12:
        return text

    ctx = ctx or {}
    templates = templates or {"partials": {}}

    def token_value(match):
        token = match.group(1).strip()
        page = ctx.get("page", {})

        if token == "lang":
            return lang

        if token == "url_prefix":
            return URL_PREFIX

        if token == "home_url":
            return page_url(locales, lang, "introduction")

        if token == "contact_action":
            return asset_url("contact.php")

        if token == "content":
            return str(ctx.get("content") or page.get("body") or page.get("main") or "")

        if token == "cards":
            return str(ctx.get("cards") or page.get("cards") or "")

        if token == "language_switcher":
            return render_language_switcher(lang, locales, page.get("key", "introduction"))

        if token == "main_menu":
            return render_main_menu(lang, locales, page.get("key", "introduction"))

        if token == "mobile_menu":
            return render_mobile_menu(lang, locales, page.get("key", "introduction"))

        if token == "privacy_policy_url":
            return page_url(locales, lang, "privacy_policy")

        if token == "common.select_page":
            return {
                "en": "Select page",
                "fr": "Sélectionner une page",
                "hr": "Odaberite stranicu",
            }.get(lang, "Select page")
        
        if token == "brand.logo_width":
            return str(get_image_info(value_from_locales(lang, "brand.logo_src", locales)).get("width", ""))
        
        if token == "brand.logo_height":
            return str(get_image_info(value_from_locales(lang, "brand.logo_src", locales)).get("height", ""))
        
        if token == "brand.logo_webp_src":
            return asset_url(get_image_info(value_from_locales(lang, "brand.logo_src", locales)).get("webp_src", ""))

        if token.startswith("partial."):
            name = token.split(".", 1)[1]
            partial = templates.get("partials", {}).get(name)
            if partial is None:
                return "{{" + token + "}}"
            return partial

        if token.startswith("page."):
            value = nested_get(page, token.split(".", 1)[1])
            return "" if value is None else str(value)

        if token.startswith("content."):
            return read_content(lang, token.split(".", 1)[1])
        
        if token.startswith("card."):
            value = nested_get(ctx.get("card", {}), token.split(".", 1)[1])
            return "" if value is None else str(value)
        
        if token.startswith("row."):
            value = nested_get(ctx.get("row", {}), token.split(".", 1)[1])
            return "" if value is None else str(value)

        if token.startswith("section."):
            value = nested_get(ctx.get("section", {}), token.split(".", 1)[1])
            return "" if value is None else str(value)

        value = value_from_locales(lang, token, locales)

        if value is None:
            return "{{" + token + "}}"
        
        if token == "brand.logo_src":
            return asset_url(str(value))

        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)

        return str(value)

    rendered = TOKEN_RE.sub(token_value, text)

    if rendered != text and TOKEN_RE.search(rendered):
        return render_text(rendered, lang, locales, ctx, templates, depth + 1)

    return rendered



def render_partial(name: str, lang: str, locales, ctx, templates) -> str:
    """Render a named partial template with the current language, locale data, and rendering context."""
    partial = templates.get("partials", {}).get(name, "")
    if not partial:
        return ""
    return render_text(partial, lang, locales, ctx, templates)



def card_group_for(page_key: str, lang: str, cards_config) -> list[str]:
    """Resolve the card keys assigned to a page, applying language-specific config and filtering disabled or unsluggable pages."""
    cards = None

    if isinstance(cards_config, dict):
        cards = cards_config.get(page_key)

    if cards is None:
        cards = PAGES_CONFIG.get("card_groups", {}).get(page_key)

    if isinstance(cards, dict):
        cards = cards.get(lang) or cards.get("en") or []

    if not isinstance(cards, list):
        cards = []

    keys = list(cards)

    if page_key == "introduction" and "the_hague_convention" not in keys:
        keys.append("the_hague_convention")

    filtered = []

    for key in keys:
        page = page_config(key)
        if page and not is_enabled(page, lang):
            continue
        if page and not page_slug(lang, key, {}):
            continue
        filtered.append(key)

    return filtered

def image_300_variant(src: str) -> str:
    """Return the expected 300x200 image variant path for a source image path."""
    m = re.match(r"^(.*?)(\.[a-zA-Z0-9]+)$", src)
    if not m:
        return src
    return f"{m.group(1)}-300x200{m.group(2)}"

def convert_to_webp(directory: str) -> None:
    """
    Converts all images in the specified directory to WebP format using ImageMagick.
    """
    for path in Path(directory).rglob("*.*"):
        if path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            webp_path = path.with_suffix(".webp")
            if not webp_path.exists():
                try:
                    subprocess.run(
                        ["convert", str(path), "-quality", "80", str(webp_path)],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    print_labeled("OK", CLR_GREEN, f"Converted {path}")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    print_labeled("WARN", CLR_YELLOW, f"error converting {path}.")
                    
def get_image_info(relative_path: str) -> dict:
    """
    Returns the width, height, and webp source of the image.
    """
    full_path = ROOT / relative_path.lstrip('/')
    if full_path.exists():
        width, height = imagesize.get(full_path)
        return {
            "width": width,
            "height": height,
            "webp_src": relative_path.rsplit('.', 1)[0] + '.webp'
        }
    return {"width": "", "height": "", "webp_src": relative_path}

def render_card(lang: str, locales, key: str, col_index: int, cols: int, templates) -> str:
    """Render one card item with localized title, image metadata, URL, layout width, and read-more label."""
    title = value_from_locales(lang, f"card_items.{key}.title", locales) or page_title(lang, key, locales)
    img_src_value = value_from_locales(lang, f"card_items.{key}.image_src", locales) or ""
    img_src = asset_url(str(img_src_value)) if img_src_value else ""
    img_alt = value_from_locales(lang, f"card_items.{key}.image_alt", locales) or ""
    img_title = value_from_locales(lang, f"card_items.{key}.image_title", locales) or img_alt
    read_more = value_from_locales(lang, "common.read_more", locales) or "READ MORE"
    href = page_url(locales, lang, key)

    width_class = {
        1: "pca-card--full",
        2: "pca-card--half",
        3: "pca-card--third",
    }.get(cols, "pca-card--third")

    src = html.escape(str(img_src), quote=True)

    srcset = ""
    if img_src:
        srcset = (
            f'srcset="{src} 360w, '
            f'{html.escape(image_300_variant(str(img_src)), quote=True)} 300w" '
            'sizes="(max-width: 360px) 100vw, 360px"'
        )
        
    image_info = get_image_info(img_src_value)

    ctx = {
        "card": {
            "width_class": width_class,
            "last": "",
            "webp_src": html.escape(str(image_info.get("webp_src", "")), quote=True),
            "image_src": src,
            "image_alt": html.escape(str(img_alt), quote=True),
            "image_title": html.escape(str(img_title)),
            "image_width": html.escape(str(image_info.get("width", "")), quote=True),
            "image_height": html.escape(str(image_info.get("height", "")), quote=True),
            "srcset": srcset,
            "title": html.escape(str(title)),
            "href": href,
            "read_more": html.escape(str(read_more)),
        }
    }

    return render_text(templates["partials"]["card"], lang, locales, ctx, templates)



def chunk_cards(keys: list[str]) -> list[list[str]]:
    """Split card keys into rows that preserve the intended 2-column or 3-column layout."""
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



def render_card_grid(
    page_key: str,
    lang: str,
    locales,
    cards_config,
    templates,
) -> str:
    """Render the full card section for a page by grouping card keys into rows and rendering each card."""
    keys = card_group_for(page_key, lang, cards_config)

    if not keys:
        return ""

    rendered_rows = []

    for row_keys in chunk_cards(keys):
        cols = len(row_keys)
        rendered_cards = []

        for col_index, key in enumerate(row_keys):
            rendered_cards.append(
                render_card(lang, locales, key, col_index, cols, templates)
            )

        row_ctx = {
            "row": {
                "cards": "\n".join(rendered_cards),
            }
        }

        rendered_rows.append(
            render_text(templates["partials"]["card_row"], lang, locales, row_ctx, templates)
        )

    section_ctx = {
        "section": {
            "id": 0 if page_key == "introduction" else 1,
            "rows": "\n".join(rendered_rows),
        }
    }

    return render_text(templates["partials"]["card_section"], lang, locales, section_ctx, templates)			



def wants_title(page: dict, template_name: str) -> bool:
    """Decide whether the page should render a visible title section for the selected template."""
    if page.get("key") == "introduction":
        return False

    if template_name == "home":
        return False

    return page.get("title", True) is not False



def section_index_for_cards(key: str, template_name: str, content_html: str) -> int:
    """Return the historical section index for card sections based on page type and intro content."""
    if key == "introduction":
        return 0

    if template_name == "cards":
        return 1

    if template_name == "cards_with_intro" and content_html.strip():
        return 2

    return 1
    
def find_images_to_preload(html: str) -> list[str]:
    patterns = [
        r'<img[^>]*\bsrc=["\']([^"\']+)["\']',
        r'<source[^>]*\bsrcset=["\']([^"\']+)["\']'
    ]
    
    images = []
    for pattern in patterns:
        images.extend(re.findall(pattern, html, re.IGNORECASE))
    return images

def render_preload(images: list[str]) -> str:
    """Render preload links for a list of image URLs."""
    return "\n".join(f'<link rel="preload" href="{img}" as="image" fetchpriority=high>' for img in images)

def render_page(lang: str, locales, page: dict, templates, cards_config, seo_config) -> None:
    """Render one localized page by combining Markdown content, cards, partials, SEO metadata, and the base template."""
    if not is_enabled(page, lang):
        return

    key = page["key"]

    content_html = read_content(lang, key)
    card_keys = card_group_for(key, lang, cards_config)
    has_cards = bool(card_keys)

    template_name = template_name_for(page, has_cards)

    has_title = wants_title(page, template_name)

    meta = page_data(locales, lang, key)
    
    page_ctx = {
        **meta,
        "url": page_url(locales, lang, key),
        "canonical_url": absolute_page_url(seo_config, locales, lang, key),
        "seo_head": render_seo_head(seo_config, locales, lang, key, meta["title"]),
        "content": content_html,
        "cards": render_card_grid(
            key,
            lang,
            locales,
            cards_config,
            templates,
        ),
        "cache_css": cache_css_link(page, template_name),
        "hero_style": hero_style_for_page(lang, locales, key),
        "hero_class": "",
        "title_section": "",
        "main": "",
        "body": "",
    }

    ctx = {
        "page": page_ctx,
        "content": "",
        "cards": page_ctx["cards"],
    }

    if has_title:
        page_ctx["title_section"] = render_partial("title_section", lang, locales, ctx, templates)

    pieces = []

    if template_name == "home":
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])

    elif template_name == "contact":
        pieces.append(render_partial("contact_form", lang, locales, ctx, templates))

    elif template_name == "cards":
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])

    elif template_name == "cards_with_intro":
        if content_html.strip():
            pieces.append(render_partial("introduction", lang, locales, ctx, templates))
        if page_ctx["cards"]:
            pieces.append(page_ctx["cards"])

    else:
        pieces.append(render_partial("article", lang, locales, ctx, templates))

    page_ctx["main"] = "\n".join(piece for piece in pieces if piece.strip())

    ctx["content"] = page_ctx["main"]
    page_ctx["body"] = render_text(templates["page"], lang, locales, ctx, templates)

    ctx["content"] = page_ctx["body"]
    full = render_text(templates["base"], lang, locales, ctx, templates)

    preload_html = render_preload(find_images_to_preload(full))
    full = full.replace("</head>", f"{preload_html}\n</head>")
    
    dst = output_path(locales, lang, key)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(full, encoding="utf-8")



def render_404_head(seo_config: dict) -> str:
    icons = seo_config.get("icons") or {}
    lines = [
        '<meta name="robots" content="noindex,follow">',
        '<meta name="description" content="Page not found.">',
    ]

    lines.extend(render_icons(seo_config, lang))

    if seo_config.get("theme_color"):
        lines.append(f'<meta name="theme-color" content="{html.escape(str(seo_config["theme_color"]), quote=True)}">')

    return "\n".join(lines)



def render_404(lang: str, locales, templates) -> None:
    """Render the localized 404 page with noindex metadata and a dedicated 404 partial."""
    title = value_from_locales(lang, "not_found.title", locales) or "404"
    message = value_from_locales(lang, "not_found.text", locales) or "Page not found."
    back_label = value_from_locales(lang, "not_found.button", locales) or {
        "en": "Back to introduction",
        "fr": "Retour à l’introduction",
        "hr": "Natrag na uvod",
    }.get(lang, "Back to introduction")

    page_ctx = {
        "key": "404",
        "title": str(title),
        "slug": "404",
        "url": f"{page_prefix(lang)}/404.html",
        "canonical_url": "",
        "seo_head": render_404_head(SEO_CONFIG),
        "content": f"<p>{html.escape(str(message))}</p>",
        "message": html.escape(str(message)),
        "back_url": html.escape(page_url(locales, lang, "introduction"), quote=True),
        "back_label": html.escape(str(back_label)),
        "cards": "",
        "cache_css": cache_css_link({"key": "404"}, "404"),
        "hero_style": "",
        "hero_class": "pca-not-found",
        "title_section": "",
        "main": "",
        "body": "",
    }

    ctx = {"page": page_ctx, "content": "", "cards": ""}

    page_ctx["title_section"] = render_partial("title_section", lang, locales, ctx, templates)
    page_ctx["main"] = render_partial("not_found", lang, locales, ctx, templates)

    ctx["content"] = page_ctx["main"]
    page_ctx["body"] = render_text(templates["page"], lang, locales, ctx, templates)

    ctx["content"] = page_ctx["body"]
    full = render_text(templates["base"], lang, locales, ctx, templates)

    dst = DIST / lang / "404.html"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(full, encoding="utf-8")



def indexable_page_keys_for_lang(lang: str) -> list[str]:
    """Return enabled non-404 page keys that may be used for indexable SEO outputs."""
    keys = []
    for page in PAGES_CONFIG.get("pages", []):
        key = page.get("key")
        if not key or not is_enabled(page, lang):
            continue
        if key == "404":
            continue
        keys.append(key)
    return keys



def all_enabled_page_keys_for_lang(lang: str) -> list[str]:
    """Return all enabled page keys for a language, including pages that may not be indexable."""
    keys = []
    for page in PAGES_CONFIG.get("pages", []):
        key = page["key"]
        if is_enabled(page, lang):
            keys.append(key)
    return keys



def render_sitemap_xml(seo_config: dict, locales, lang: str) -> str:
    """Render a localized sitemap.xml file with canonical URLs and hreflang alternates."""
    rows = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    ]

    for key in all_enabled_page_keys_for_lang(lang):
        canonical = absolute_page_url(seo_config, locales, lang, key)
        rows.append("  <url>")
        rows.append(f"    <loc>{html.escape(canonical)}</loc>")
        lastmod = page_lastmod(seo_config, lang, key)
        if lastmod:
            rows.append(f"    <lastmod>{html.escape(lastmod)}</lastmod>")
    
        for alt_lang in enabled_alternate_langs(key):
            alt_url = absolute_page_url(seo_config, locales, alt_lang, key)
            hreflang = page_hreflang(seo_config, alt_lang)
            rows.append(
                f'    <xhtml:link rel="alternate" hreflang="{html.escape(hreflang)}" href="{html.escape(alt_url)}" />'
            )

        x_default_lang = seo_config.get("x_default") or "en"
        if x_default_lang in enabled_alternate_langs(key):
            x_default_url = absolute_page_url(seo_config, locales, x_default_lang, key)
            rows.append(
                f'    <xhtml:link rel="alternate" hreflang="x-default" href="{html.escape(x_default_url)}" />'
            )

        rows.append("  </url>")

    rows.append("</urlset>")
    return "\n".join(rows) + "\n"



def write_extra_seo_files(seo_config: dict, locales) -> None:
    """Write sitemap.xml, robots.txt, and site.webmanifest files into each language output directory."""
    for lang in LANGS:
        lang_root = DIST / lang
        lang_root.mkdir(parents=True, exist_ok=True)

        base = site_base_url(seo_config, lang, locales)

        (lang_root / "sitemap.xml").write_text(
            render_sitemap_xml(seo_config, locales, lang),
            encoding="utf-8"
        )

        (lang_root / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\n\nSitemap: {base}/sitemap.xml\n",
            encoding="utf-8"
        )

        manifest = {
            "name": value_from_locales(lang, "site_name", locales) or "Poland Child Abduction",
            "short_name": value_from_locales(lang, "site_name", locales) or "PCA",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#ffffff",
            "theme_color": seo_config.get("theme_color") or "#317041",
            "icons": [
                {
                    "src": asset_url("apple-touch-icon.png"),
                    "sizes": "180x180",
                    "type": "image/png"
                }
            ]
        }

        (lang_root / "site.webmanifest").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )



def htaccess_404_path(lang: str) -> str:
    """Return the public 404 path used by Apache for this language output."""
    prefix = page_prefix(lang)
    return f"{prefix}/404.html"



def render_htaccess(lang: str, seo_config: dict, locales) -> str:
    """Render Apache .htaccess rules for one generated language directory."""
    error_404 = htaccess_404_path(lang)

    return f"""# Generated by the PCA static site builder.
# Do not edit this file directly unless you also update the generator.

Options -Indexes
DirectoryIndex index.html index.php

ErrorDocument 404 {error_404}

<IfModule mod_rewrite.c>
RewriteEngine On

# Force HTTPS.
RewriteCond %{{HTTPS}} !=on
RewriteRule ^ https://%{{HTTP_HOST}}%{{REQUEST_URI}} [R=301,L]
</IfModule>

<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
Header always set Referrer-Policy "strict-origin-when-cross-origin"
Header always set Permissions-Policy "geolocation=(), microphone=(), camera=()"
Header always set X-Frame-Options "SAMEORIGIN"

Header always set Content-Security-Policy "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; font-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'"

<FilesMatch "\.(jpg|jpeg|png|gif|css|js|woff2|woff|ttf)$">
    Header set Cache-Control "public, max-age=31536000, immutable"
</FilesMatch>
</IfModule>

<IfModule mod_deflate.c>
AddOutputFilterByType DEFLATE text/html text/plain text/css text/xml application/xml application/xhtml+xml application/rss+xml application/javascript application/json image/svg+xml
</IfModule>

<IfModule mod_expires.c>
ExpiresActive On

ExpiresByType text/html "access plus 0 seconds"
ExpiresByType text/css "access plus 1 month"
ExpiresByType application/javascript "access plus 1 month"
ExpiresByType image/svg+xml "access plus 1 month"
ExpiresByType image/png "access plus 1 year"
ExpiresByType image/jpeg "access plus 1 year"
ExpiresByType image/webp "access plus 1 year"
ExpiresByType image/gif "access plus 1 year"
ExpiresByType font/woff2 "access plus 1 year"
</IfModule>

<IfModule mod_headers.c>
<FilesMatch "\\.(?:css|js|png|jpg|jpeg|gif|webp|svg|woff2)$">
Header set Cache-Control "public, max-age=31536000"
</FilesMatch>

<FilesMatch "\\.(?:html|htm|php)$">
Header set Cache-Control "no-cache, must-revalidate"
</FilesMatch>
</IfModule>

# Block private/config/source-like files.
<FilesMatch "(^\\.|\\.env$|composer\\.(json|lock)$|package(-lock)?\\.json$|yarn\\.lock$|pnpm-lock\\.yaml$|.*\\.(md|py|sh|sql|bak|old|orig|log)$)">
Require all denied
</FilesMatch>
"""



def write_htaccess_files(seo_config: dict, locales) -> None:
    """Write one public .htaccess file into each generated language directory."""
    for lang in LANGS:
        lang_root = DIST / lang
        lang_root.mkdir(parents=True, exist_ok=True)

        (lang_root / ".htaccess").write_text(
            render_htaccess(lang, seo_config, locales),
            encoding="utf-8",
        )
        


def copy_path(src: Path, dst: Path) -> None:
    """Copy a file or directory to the destination, creating parent directories when needed."""
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)



def copy_assets_to(dst: Path) -> None:
    assets_src = ROOT / "assets"
    assets_dst = dst / "assets"

    if assets_src.exists():
        for item in assets_src.iterdir():
            if item.name == "common":
                continue
            copy_path(item, assets_dst / item.name)



def copy_static(lang: str) -> None:
    """Copy public PHP files, and private contact config into one language output directory.
    Copy assets if not LANG_IN_URL, else assets are expected to be copied later."""
    lang_root = DIST / lang
    lang_root.mkdir(parents=True, exist_ok=True)

    if not LANG_IN_URL:
        copy_assets_to(lang_root)

    for php_src in ROOT.glob("*.php"):
        if php_src.name == "pca-contact-config.php":
            continue
        copy_path(php_src, lang_root / php_src.name)

    private_dir = lang_root / ".private"
    private_dir.mkdir(parents=True, exist_ok=True)

    config_src = ROOT / "pca-contact-config.php"
    if config_src.exists():
        copy_path(config_src, private_dir / "pca-contact-config.php")

    (private_dir / ".htaccess").write_text("Require all denied\n", encoding="utf-8")



def render_templates(locales):
    """Load config, templates, cards, and SEO settings, then render every enabled page for every language."""
    global PAGES_CONFIG, PAGES_BY_KEY, SEO_CONFIG

    pages_path = ROOT / "config" / "pages.json"
    cards_path = ROOT / "config" / "cards.json"
    seo_path = ROOT / "config" / "seo.json"

    if not pages_path.exists():
        raise SystemExit(f"Missing config: {display_path(pages_path, ROOT)}")

    PAGES_CONFIG = load_json(pages_path)
    PAGES_BY_KEY = {page["key"]: page for page in PAGES_CONFIG.get("pages", [])}

    cards_config = load_json(cards_path) if cards_path.exists() else {}
    SEO_CONFIG = load_seo_config()
    templates = load_templates()

    for lang in LANGS:
        for page in PAGES_CONFIG.get("pages", []):
            render_page(lang, locales, page, templates, cards_config, SEO_CONFIG)
        render_404(lang, locales, templates)
        copy_static(lang)
    
    if LANG_IN_URL:
        copy_assets_to(DIST)

    write_extra_seo_files(SEO_CONFIG, locales)
    write_htaccess_files(SEO_CONFIG, locales)


def build(root) -> None:
    configure_paths(root)

    print_section("Build static site")
    print(color(f"Root: {display_path(ROOT, ROOT.parent)}", CLR_WHITE))
    print(color(f"Dist: {display_path(DIST, ROOT.parent)}", CLR_WHITE))

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)

    locales = {lang: load_locale(lang) for lang in LANGS}

    render_templates(locales)

    for lang in LANGS:
        (DIST / lang).mkdir(parents=True, exist_ok=True)

    (DIST / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=/en/"><link rel="canonical" href="/en/"><title>Redirecting…</title>',
        encoding="utf-8",
    )

    convert_to_webp(str(DIST))
    print_labeled("OK", CLR_GREEN, f"built {display_path(DIST, ROOT.parent)}")



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PCA static site.")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    build(args.root)



if __name__ == "__main__":
    main()
