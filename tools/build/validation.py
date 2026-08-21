"""Site model, per-site extension, and locale validation."""

from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from common import CLR_GREEN, CLR_RED, CLR_WHITE, CLR_YELLOW, color, display_path, load_json, print_group, print_labeled, print_section

LEGACY_SHARED_PAGE_FIELDS = {"enabled", "titles", "slugs"}
REQUIRED_SITE_FIELDS = ("url", "hreflang", "og_locale", "social_image")
NON_CONTENT_TEMPLATES = {"home", "home_cards", "contact", "contact_page", "cards", "cards_page"}


def _load_sites(root: Path) -> dict[str, dict]:
    sites_dir = root / "sites"
    return {path.stem: load_json(path) for path in sorted(sites_dir.glob("*.json"))} if sites_dir.is_dir() else {}


def _load_locales(root: Path) -> dict[str, dict]:
    return {path.stem: load_json(path) for path in sorted((root / "locales").glob("*.json"))}


def _extra_pages(site: dict) -> list[dict]:
    extra = site.get("extra_pages", []) if isinstance(site, dict) else []
    if isinstance(extra, dict):
        return [{"key": key, **value} for key, value in extra.items() if isinstance(value, dict)]
    if isinstance(extra, list):
        return [page for page in extra if isinstance(page, dict)]
    return []


def _check_graph(pages: list[dict], label: str, errors: list[str]) -> dict[str, dict]:
    by_key: dict[str, dict] = {}
    counts = defaultdict(int)
    for page in pages:
        key = page.get("key")
        if not key:
            errors.append(f"{label}: page without key")
            continue
        counts[key] += 1
        by_key[key] = page
        if not page.get("template"):
            errors.append(f"{label}: page '{key}' missing template")
    for key, count in counts.items():
        if count != 1:
            errors.append(f"{label}: duplicate page key '{key}'")
    for key, page in by_key.items():
        parent = page.get("parent")
        if parent and parent not in by_key:
            errors.append(f"{label}: page '{key}' references missing parent '{parent}'")
    for key in by_key:
        seen: set[str] = set()
        current = key
        while current:
            if current in seen:
                errors.append(f"{label}: hierarchy cycle involving '{current}'")
                break
            seen.add(current)
            page = by_key.get(current)
            current = str(page.get("parent") or "") if page else ""
    return by_key


def _slug_segment(entry: dict) -> str:
    raw = str(entry.get("slug") or "").strip("/")
    return raw.rsplit("/", 1)[-1] if raw else ""


def _resolved_slug(key: str, by_key: dict[str, dict], locale_pages: dict) -> str:
    if key == "introduction":
        return ""
    parts: list[str] = []
    seen: set[str] = set()
    current = key
    while current and current != "introduction":
        if current in seen:
            return ""
        seen.add(current)
        entry = locale_pages.get(current) or {}
        segment = _slug_segment(entry)
        if segment:
            parts.append(segment)
        page = by_key.get(current) or {}
        current = str(page.get("parent") or "")
    return "/".join(reversed(parts))


def _requires_content(page: dict) -> bool:
    return str(page.get("template") or "content") not in NON_CONTENT_TEMPLATES


def _validate_site_identity(lang: str, site: dict, errors: list[str]) -> None:
    for field in REQUIRED_SITE_FIELDS:
        value = site.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Site '{lang}' missing required {field}")
    url = str(site.get("url") or "").strip()
    parsed = urlsplit(url)
    if url and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
        errors.append(f"Site '{lang}' url must be an absolute HTTP(S) URL")


def validate(root, *, strict: bool = False, autofix_prompt: bool = True) -> None:
    root = Path(root).expanduser().resolve()
    pages_path = root / "config" / "pages.json"
    locales_dir = root / "locales"
    errors: list[str] = []
    warnings: list[str] = []
    term_width = min(shutil.get_terminal_size((120, 20)).columns, 140)

    if not root.is_dir():
        print_labeled("ERROR", CLR_RED, f"site source root not found: {display_path(root, root.parent)}")
        raise SystemExit(2)
    if not pages_path.is_file():
        print_labeled("ERROR", CLR_RED, f"pages config not found: {display_path(pages_path, root.parent)}")
        raise SystemExit(2)
    if not locales_dir.is_dir():
        print_labeled("ERROR", CLR_RED, f"locales directory not found: {display_path(locales_dir, root.parent)}")
        raise SystemExit(2)

    pages_data = load_json(pages_path)
    if pages_data.get("schema_version") != 2:
        errors.append("config/pages.json must declare schema_version 2")
    shared_pages = pages_data.get("pages", [])
    for page in shared_pages:
        stale = LEGACY_SHARED_PAGE_FIELDS.intersection(page.keys()) if isinstance(page, dict) else set()
        if stale:
            errors.append(f"Shared page '{page.get('key')}' contains locale-owned fields: {sorted(stale)}")
    if "card_groups" in pages_data:
        errors.append("config/pages.json must not contain card_groups; use parent relationships or config/cards.json")
    shared_by_key = _check_graph(shared_pages, "shared model", errors)

    sites = _load_sites(root)
    locales = _load_locales(root)
    site_codes = list(sites) if sites else list(locales)
    if sites and set(sites) != set(locales):
        for code in sorted(set(sites) - set(locales)):
            errors.append(f"Site '{code}' has sites/{code}.json but no locales/{code}.json")
        for code in sorted(set(locales) - set(sites)):
            errors.append(f"Locale '{code}' has no sites/{code}.json")

    for lang in site_codes:
        locale = locales.get(lang, {})
        locale_pages = locale.get("pages", {}) if isinstance(locale, dict) else {}
        site = sites.get(lang, {})
        _validate_site_identity(lang, site if isinstance(site, dict) else {}, errors)
        locale_seo = locale.get("seo") if isinstance(locale, dict) else None
        if not isinstance(locale_seo, dict):
            errors.append(f"Locale '{lang}' missing seo object")
            locale_seo = {}
        default_description = locale_seo.get("default_description")
        if not isinstance(default_description, str) or not default_description.strip():
            errors.append(f"Locale '{lang}' seo.default_description is required")
        seo_descriptions = locale_seo.get("descriptions")
        if not isinstance(seo_descriptions, dict):
            errors.append(f"Locale '{lang}' seo.descriptions must be an object")
            seo_descriptions = {}
        effective = [dict(page) for page in shared_pages if isinstance(page, dict)]
        extra = _extra_pages(site)
        shared_keys = set(shared_by_key)
        for page in extra:
            key = page.get("key")
            if key in shared_keys:
                errors.append(f"Site '{lang}' extra page '{key}' collides with a shared page")
            effective.append(page)
        by_key = _check_graph(effective, f"site '{lang}'", errors)
        urls = defaultdict(list)
        for key, page in by_key.items():
            entry = locale_pages.get(key)
            if not isinstance(entry, dict):
                errors.append(f"Locale '{lang}' missing pages.{key}")
                continue
            if entry.get("enabled", True) is False:
                continue
            if not str(entry.get("title") or "").strip():
                errors.append(f"Locale '{lang}' pages.{key} missing title")
            if key != "introduction" and not str(entry.get("slug") or "").strip("/"):
                errors.append(f"Locale '{lang}' pages.{key} missing slug")
            description = seo_descriptions.get(key)
            if not isinstance(description, str) or not description.strip():
                errors.append(f"Locale '{lang}' seo.descriptions.{key} is required")
            if _requires_content(page):
                content_path = root / "content" / lang / f"{key}.md"
                if not content_path.is_file():
                    errors.append(f"Locale '{lang}' missing content/{lang}/{key}.md")
                elif not content_path.read_text(encoding="utf-8").strip():
                    errors.append(f"Locale '{lang}' content/{lang}/{key}.md is empty")

            # Locale parent fields belong to the pre-v2 architecture. They are never
            # structural input, even when stale or contradictory: the effective page
            # graph is the single source of truth for hierarchy.
            if "parent" in entry:
                warnings.append(f"Locale '{lang}' pages.{key}.parent is legacy duplicated structure and is ignored")

            raw_slug = str(entry.get("slug") or "").strip("/")
            if page.get("parent") and "/" in raw_slug:
                warnings.append(f"Locale '{lang}' pages.{key}.slug stores a legacy full path; only its final segment is used")
            resolved = _resolved_slug(key, by_key, locale_pages)
            if resolved or key == "introduction":
                urls[resolved].append(key)

        for slug, keys in urls.items():
            if len(keys) > 1:
                errors.append(f"Locale '{lang}' duplicate resolved route '{slug}' for {keys}")

        extra_locale_keys = set(locale_pages) - set(by_key)
        enabled_extras = [key for key in extra_locale_keys if (locale_pages.get(key) or {}).get("enabled", True) is not False]
        if enabled_extras:
            errors.append(f"Locale '{lang}' enables pages not declared by shared model or site manifest: {sorted(enabled_extras)}")

    print_section("Site Check Report", term_width)
    print(color(f"Source:        {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Sites found:   {', '.join(site_codes)}", CLR_WHITE))
    print(color(f"Shared pages:  {len(shared_pages)}", CLR_WHITE))
    print_group("Warnings", warnings, "WARN", CLR_YELLOW)
    print_group("Critical issues", errors, "ERROR", CLR_RED)
    if errors or (strict and warnings):
        raise SystemExit(1)
    print_labeled("OK", CLR_GREEN, "site model and locale packages look good.")
