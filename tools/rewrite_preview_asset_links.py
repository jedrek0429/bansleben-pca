"""Rewrite preview asset URLs to include the language directory.

The normal production build serves each language from its own domain, so root-relative
asset URLs such as /assets/file.css are correct after publishing into each language
root. PR previews serve all languages under one preview prefix, for example:

    /pr-12/en/
    /pr-12/fr/
    /pr-12/hr/

The build already writes the pages into language directories, but some asset URLs are
initially generated as /pr-12/assets/... instead of /pr-12/en/assets/.... This helper
rewrites those generated preview HTML files after build.py and before publish.py.
"""

from __future__ import annotations

import argparse
from pathlib import Path

LANGS = ["en", "fr", "hr"]
STATIC_ROOTS = ["assets", "wp-content", "wp-includes"]


def normalize_prefix(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith("/"):
        value = "/" + value
    return value


def rewrite_text(text: str, prefix: str, lang: str) -> str:
    for root in STATIC_ROOTS:
        text = text.replace(f'{prefix}/{root}/', f'{prefix}/{lang}/{root}/')
        text = text.replace(f'{prefix}/{lang}/{lang}/{root}/', f'{prefix}/{lang}/{root}/')
    text = text.replace(f'{prefix}/contact.php', f'{prefix}/{lang}/contact.php')
    text = text.replace(f'{prefix}/{lang}/{lang}/contact.php', f'{prefix}/{lang}/contact.php')
    return text


def rewrite_dist(dist: Path, prefix: str) -> int:
    prefix = normalize_prefix(prefix)
    if not prefix:
        return 0

    changed = 0
    for lang in LANGS:
        lang_root = dist / lang
        if not lang_root.exists():
            continue
        for path in lang_root.rglob("*.html"):
            original = path.read_text(encoding="utf-8")
            updated = rewrite_text(original, prefix, lang)
            if updated != original:
                path.write_text(updated, encoding="utf-8")
                changed += 1
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rewrite preview asset URLs under language roots.")
    parser.add_argument("--dist", required=True, help="site-dist directory")
    parser.add_argument("--url-prefix", required=True, help="preview URL prefix, for example /pr-12")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    changed = rewrite_dist(Path(args.dist).expanduser().resolve(), args.url_prefix)
    print(f"Rewrote preview asset links in {changed} HTML files.")


if __name__ == "__main__":
    main()
