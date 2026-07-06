"""Autofix locale JSON files from pages.json and en.json."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from common import CLR_GREEN, CLR_RED, CLR_WHITE, CLR_YELLOW, color, display_path, load_json, print_labeled, print_section


def write_json(path: Path, data: Any) -> None:
    backup = path.with_name(path.name + ".bak")
    if path.exists():
        shutil.copyfile(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def locale_enabled_for_page(page: dict, lang: str, fallback_langs: set[str]) -> bool:
    enabled = page.get("enabled")
    if not enabled:
        return lang in fallback_langs
    return lang in set(enabled)


def autofix_locales(root) -> None:
    root = Path(root).expanduser().resolve()
    pages_path = root / "config" / "pages.json"
    locales_dir = root / "locales"

    print_section("Locale Autofix Report")
    print(color(f"Source:  {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Locales: {display_path(locales_dir, root.parent)}", CLR_WHITE))

    if not root.is_dir():
        print_labeled("ERROR", CLR_RED, f"site source root not found: {display_path(root, root.parent)}")
        raise SystemExit(2)
    if not pages_path.is_file():
        print_labeled("ERROR", CLR_RED, f"pages.json not found: {display_path(pages_path, root.parent)}")
        raise SystemExit(2)
    if not locales_dir.is_dir():
        print_labeled("ERROR", CLR_RED, f"locales directory not found: {display_path(locales_dir, root.parent)}")
        raise SystemExit(2)

    pages_data = load_json(pages_path)
    pages = pages_data.get("pages", [])
    configured_langs = set(pages_data.get("langs") or pages_data.get("languages") or [])
    locale_langs = {path.stem for path in locales_dir.glob("*.json")}
    fallback_langs = configured_langs or locale_langs

    en_path = locales_dir / "en.json"
    if not en_path.is_file():
        print_labeled("ERROR", CLR_RED, "en.json missing in locales")
        raise SystemExit(1)
    en = load_json(en_path)
    en_card_items = en.get("card_items", {}) if isinstance(en, dict) else {}

    changed = 0
    for path in sorted(locales_dir.glob("*.json")):
        name = path.name
        try:
            data = load_json(path)
        except Exception as exc:
            print_labeled("WARN", CLR_YELLOW, f"Skipping {name}: failed to parse ({exc})")
            continue

        lang = data.get("lang") or os.path.splitext(name)[0]
        modified = False
        pages_obj = data.setdefault("pages", {})
        card_items = data.setdefault("card_items", {})

        for page in pages:
            key = page.get("key")
            if not key:
                continue
            if not locale_enabled_for_page(page, lang, fallback_langs):
                continue

            entry = pages_obj.get(key)
            if entry is None:
                entry = {}
                pages_obj[key] = entry
                modified = True

            if not entry.get("enabled"):
                entry["enabled"] = True
                modified = True

            titles = page.get("titles", {})
            expected_title = titles.get(lang) or entry.get("title") or ""
            if (entry.get("title") or "") != expected_title:
                entry["title"] = expected_title
                modified = True

            slugs = page.get("slugs", {})
            expected_slug = slugs.get(lang, "")
            if (entry.get("slug") or "") != expected_slug:
                entry["slug"] = expected_slug
                modified = True

            if "parent" not in entry and page.get("parent") is not None:
                entry["parent"] = page.get("parent")
                modified = True

            en_card = en_card_items.get(key)
            if en_card:
                card = card_items.get(key)
                if card is None:
                    card = {}
                    card_items[key] = card
                    modified = True

                page_title = entry.get("title") or ""
                for field in ("title", "image_alt", "image_title"):
                    if not card.get(field):
                        card[field] = page_title
                        modified = True

                en_image = en_card.get("image_src")
                if en_image and card.get("image_src") != en_image:
                    card["image_src"] = en_image
                    modified = True

        if modified:
            print_labeled("OK", CLR_GREEN, f"Updating {name} (backup -> {path}.bak)")
            write_json(path, data)
            changed += 1

    if changed:
        print_labeled("OK", CLR_GREEN, f"Autofix completed; {changed} locale file(s) updated.")
    else:
        print_labeled("OK", CLR_GREEN, "Autofix completed; no changes needed.")
