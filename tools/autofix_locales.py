#!/usr/bin/env python3
"""Autofix locale JSON files to match SSOT (`config/pages.json` and `locales/en.json`).

This script will:
- For each page enabled in `pages.json`, ensure each locale file has a `pages` entry
  with `enabled: true`, `title` and `slug` matching `pages.json`.
- Ensure `card_items` exist for enabled pages and that `image_src` matches `en.json` when present.
- Create backups of modified locale files as `<file>.bak` before writing.

Usage: run from site-src root (or specify `--root path/to/site-src`)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

from common import CLR_GREEN, CLR_RED, CLR_WHITE, color, display_path, load_json, print_labeled, print_section


def write_json(path: Path, data: Any) -> None:
    # backup
    bak = str(path) + ".bak"
    try:
        shutil.copyfile(path, bak)
    except Exception:
        # if file doesn't exist yet, ignore
        pass
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Autofix locale JSON files to match pages.json and locales/en.json."
    )
    parser.add_argument("--root", default=".", help="site-src root, default: current directory")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    cfg_pages = root / "config" / "pages.json"
    locales_dir = root / "locales"

    print_section("Locale Autofix Report")
    print(color(f"Source: {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Locales: {display_path(locales_dir, root.parent)}", CLR_WHITE))

    if not root.is_dir():
        print_labeled("ERROR", CLR_RED, f"site-src not found: {display_path(root, root.parent)}")
        sys.exit(2)
    if not cfg_pages.is_file():
        print_labeled("ERROR", CLR_RED, f"pages.json not found: {display_path(cfg_pages, root.parent)}")
        sys.exit(2)
    if not locales_dir.is_dir():
        print_labeled("ERROR", CLR_RED, f"locales dir not found: {display_path(locales_dir, root.parent)}")
        sys.exit(2)

    pages_data = load_json(cfg_pages)
    pages = pages_data.get("pages", [])

    # load en.json as source of truth for card_items image_src
    en_path = locales_dir / "en.json"
    if not en_path.is_file():
        print_labeled("ERROR", CLR_RED, "en.json missing in locales")
        sys.exit(1)
    en = load_json(en_path)
    en_card_items = en.get("card_items", {})

    # iterate locale files
    for path in sorted(locales_dir.glob("*.json")):
        name = path.name
        try:
            data = load_json(path)
        except Exception as e:
            print_labeled("WARN", CLR_YELLOW, f"Skipping {name}: failed to parse ({e})")
            continue

        lang = data.get("lang") or os.path.splitext(name)[0]
        modified = False

        pages_obj: Dict[str, dict] = data.setdefault("pages", {})
        card_items: Dict[str, dict] = data.setdefault("card_items", {})

        for p in pages:
            key = p.get("key")
            if not key:
                continue
            enabled_locales = set(p.get("enabled", []))
            if lang not in enabled_locales:
                # ensure locale does not have enabled=true for this page (we don't remove entries)
                continue

            # ensure page entry exists
            entry = pages_obj.get(key)
            if entry is None:
                entry = {}
                pages_obj[key] = entry
                modified = True

            # enabled
            if not entry.get("enabled"):
                entry["enabled"] = True
                modified = True

            # title: prefer pages.json titles if present
            titles = p.get("titles", {})
            expected_title = titles.get(lang) or entry.get("title") or ""
            if (entry.get("title") or "") != expected_title:
                entry["title"] = expected_title
                modified = True

            # slug: sync from pages.json
            slugs = p.get("slugs", {})
            expected_slug = slugs.get(lang, "")
            if (entry.get("slug") or "") != expected_slug:
                entry["slug"] = expected_slug
                modified = True

            # parent: copy if missing
            if "parent" not in entry and p.get("parent") is not None:
                entry["parent"] = p.get("parent")
                modified = True

            # card items: if en has card for this key, ensure locale has card and image_src matches en
            en_card = en_card_items.get(key)
            if en_card:
                card = card_items.get(key)
                if card is None:
                    card = {}
                    card_items[key] = card
                    modified = True

                # Ensure required keys exist: title, image_alt, image_title
                # Provide sensible defaults from page title
                page_title = entry.get("title") or ""
                for field in ("title", "image_alt", "image_title"):
                    if not card.get(field):
                        card[field] = page_title
                        modified = True

                en_image = en_card.get("image_src")
                if en_image:
                    if card.get("image_src") != en_image:
                        card["image_src"] = en_image
                        modified = True

        if modified:
            print_labeled("OK", CLR_GREEN, f"Updating {name} (backup -> {path}.bak)")
            try:
                write_json(path, data)
            except Exception as e:
                print_labeled("ERROR", CLR_RED, f"Failed to write {name}: {e}")
                sys.exit(1)

    print_labeled("OK", CLR_GREEN, "Autofix completed.")


if __name__ == "__main__":
    main()
