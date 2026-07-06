"""Site configuration and locale validation."""

from __future__ import annotations

import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from autofix import autofix_locales
from common import CLR_GREEN, CLR_RED, CLR_WHITE, CLR_YELLOW, color, display_path, load_json, print_group, print_labeled, print_section


def locale_files(locales_dir: Path) -> list[Path]:
    return sorted(locales_dir / name for name in os.listdir(locales_dir) if name.endswith(".json"))


def locale_set(page: dict, fallback_langs: set[str]) -> set[str]:
    enabled = page.get("enabled")
    if not enabled:
        return set(fallback_langs)
    return {str(lang) for lang in enabled}


def page_enabled(page: dict, lang: str) -> bool:
    enabled = page.get("enabled")
    if not enabled:
        return True
    return lang in enabled


def should_prompt_for_autofix(autofix_prompt: bool) -> bool:
    return bool(autofix_prompt and sys.stdin.isatty())


def prompt_autofix_locales(root: Path) -> bool:
    answer = input("Run utils autofix-locales now? [Y/n] ").strip().lower()
    if answer in {"", "y", "yes"}:
        autofix_locales(root)
        return True
    return False


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
    locales = {}
    for path in locale_files(locales_dir):
        data = load_json(path)
        lang = data.get("lang") or path.stem
        locales[lang] = data

    pages = pages_data.get("pages", [])
    page_by_key = {}
    page_key_counts = defaultdict(int)
    configured_langs = set(pages_data.get("langs") or pages_data.get("languages") or [])
    enabled_langs = set()

    for page in pages:
        key = page.get("key")
        if not key:
            errors.append("Found page without a key in pages.json")
            continue
        page_key_counts[key] += 1
        page_by_key[key] = page
        if "template" not in page:
            errors.append(f"Page '{key}' missing template in pages.json")
        for lang in page.get("enabled", []) or []:
            enabled_langs.add(lang)

    for key, count in page_key_counts.items():
        if count != 1:
            errors.append(f"Duplicate page key in pages.json: {key}")

    expected_langs = configured_langs or enabled_langs or set(locales.keys())
    for lang in sorted(expected_langs):
        if lang not in locales:
            errors.append(f"Locale '{lang}' is referenced but locales/{lang}.json is missing")

    if "en" not in locales:
        errors.append("locales/en.json is required")

    fallback_langs = set(expected_langs or locales.keys())
    for page in pages:
        key = page.get("key")
        if not key:
            continue
        parent = page.get("parent")
        if parent and parent not in page_by_key:
            errors.append(f"Page '{key}' references missing parent '{parent}'")
        if parent and parent in page_by_key:
            child_langs = locale_set(page, fallback_langs)
            parent_langs = locale_set(page_by_key[parent], fallback_langs)
            missing = child_langs - parent_langs
            if missing:
                errors.append(f"Parent '{parent}' is not enabled for locales {sorted(missing)} required by child '{key}'")

    en = locales.get("en", {})
    en_top_keys = set(en.keys())
    en_card_items = en.get("card_items", {}) if isinstance(en, dict) else {}

    for lang, data in locales.items():
        extra_top = set(data.keys()) - en_top_keys if en_top_keys else set()
        if extra_top:
            warnings.append(f"Locale '{lang}' has extra top-level keys not in en.json: {sorted(extra_top)}")
        pages_obj = data.get("pages", {})
        card_items = data.get("card_items", {})
        slug_map = defaultdict(list)
        title_map = defaultdict(list)
        for page in pages:
            key = page.get("key")
            if not key:
                continue
            entry = pages_obj.get(key)
            if page_enabled(page, lang):
                if entry is None:
                    errors.append(f"Locale '{lang}' missing page entry for enabled page '{key}'")
                    continue
                if not entry.get("title"):
                    errors.append(f"Locale '{lang}' pages.{key} missing title")
                expected_slug = (page.get("slugs") or {}).get(lang, "")
                if entry.get("slug", "") != expected_slug:
                    errors.append(f"Locale '{lang}' pages.{key}.slug mismatch")
                en_card = en_card_items.get(key, {}) if isinstance(en_card_items, dict) else {}
                if en_card and key not in card_items:
                    errors.append(f"Locale '{lang}' missing card_items entry for enabled page '{key}'")
            if entry and entry.get("enabled"):
                slug = entry.get("slug", "")
                title = (entry.get("title") or "").strip()
                if slug:
                    slug_map[slug].append(key)
                if title:
                    title_map[title].append(key)
        for slug, keys in slug_map.items():
            if len(keys) > 1:
                errors.append(f"Locale '{lang}' duplicate slug '{slug}' for pages {keys}")
        for title, keys in title_map.items():
            if len(keys) > 1:
                warnings.append(f"Locale '{lang}' duplicate title '{title}' for pages {keys}")

    print_section("Site Check Report", term_width)
    print(color(f"Source:        {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Locales found: {', '.join(sorted(locales.keys()))}", CLR_WHITE))
    print(color(f"Pages checked: {len(pages)}", CLR_WHITE))
    print_group("Warnings", warnings, "WARN", CLR_YELLOW)
    print_group("Critical issues", errors, "ERROR", CLR_RED)

    failed = bool(errors or (strict and warnings))
    if failed:
        if should_prompt_for_autofix(autofix_prompt) and prompt_autofix_locales(root):
            print_labeled("INFO", CLR_YELLOW, "Autofix ran; validating again.")
            validate(root, strict=strict, autofix_prompt=False)
            return
        raise SystemExit(1)
    print_labeled("OK", CLR_GREEN, "site config and locales look good.")
