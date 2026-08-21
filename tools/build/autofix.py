"""Locale normalization utilities for the schema-v2 site model."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, CLR_WHITE, color, display_path, load_json, print_labeled, print_section


def write_json(path: Path, data) -> None:
    backup = path.with_name(path.name + ".bak")
    if path.exists():
        shutil.copyfile(path, backup)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def autofix_locales(root) -> None:
    """Remove structural duplication left by the pre-v2 locale format without inventing translations."""
    root = Path(root).expanduser().resolve()
    pages_path = root / "config" / "pages.json"
    locales_dir = root / "locales"
    print_section("Locale Normalization Report")
    print(color(f"Source:  {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Locales: {display_path(locales_dir, root.parent)}", CLR_WHITE))
    if not pages_path.is_file() or not locales_dir.is_dir():
        print_labeled("ERROR", CLR_RED, "config/pages.json and locales/ are required")
        raise SystemExit(2)
    pages = load_json(pages_path).get("pages", [])
    shared = {page.get("key"): page for page in pages if isinstance(page, dict) and page.get("key")}
    changed = 0
    for path in sorted(locales_dir.glob("*.json")):
        data = load_json(path)
        locale_pages = data.get("pages", {}) if isinstance(data, dict) else {}
        modified = False
        if isinstance(locale_pages, dict):
            for key, entry in locale_pages.items():
                if not isinstance(entry, dict):
                    continue
                shared_page = shared.get(key)
                if shared_page and "parent" in entry:
                    del entry["parent"]
                    modified = True
                raw = str(entry.get("slug") or "").strip("/")
                parent = shared_page.get("parent") if shared_page else entry.get("parent")
                if parent and "/" in raw:
                    entry["slug"] = raw.rsplit("/", 1)[-1]
                    modified = True
        if modified:
            write_json(path, data)
            print_labeled("OK", CLR_GREEN, f"Normalized {path.name} (backup -> {path.name}.bak)")
            changed += 1
    print_labeled("OK", CLR_GREEN, f"Normalization completed; {changed} locale file(s) updated.")
