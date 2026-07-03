"""Finalize a GitHub Pages PR preview directory."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT_ITEMS = ("assets", "wp-content", "wp-includes")
ROOT_PREFIXES = tuple(f"/{item}/" for item in ROOT_ITEMS)


def normalize_url_prefix(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if value and not value.startswith("/"):
        value = "/" + value
    return value


def copy_item(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def expose_root_assets(preview_dir: Path, source_lang: str) -> None:
    source_dir = preview_dir / source_lang
    if not source_dir.is_dir():
        raise SystemExit(f"Missing preview source language directory: {source_dir}")
    for item in ROOT_ITEMS:
        copy_item(source_dir / item, preview_dir / item)


def rewrite_html_urls(preview_dir: Path, url_prefix: str) -> None:
    url_prefix = normalize_url_prefix(url_prefix)
    if not url_prefix:
        return

    for path in preview_dir.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        updated = text

        for root_prefix in ROOT_PREFIXES:
            replacement = url_prefix + root_prefix

            for attr in ("href", "src", "srcset", "content"):
                updated = updated.replace(f'{attr}="{root_prefix}', f'{attr}="{replacement}')
                updated = updated.replace(f"{attr}='{root_prefix}", f"{attr}='{replacement}")

            updated = updated.replace(f"url({root_prefix}", f"url({replacement}")
            updated = updated.replace(f"url('{root_prefix}", f"url('{replacement}")
            updated = updated.replace(f'url("{root_prefix}', f'url("{replacement}')

        if updated != text:
            path.write_text(updated, encoding="utf-8")


def write_index(preview_dir: Path, url_prefix: str) -> None:
    target = normalize_url_prefix(url_prefix) + "/en/"
    preview_dir.mkdir(parents=True, exist_ok=True)
    (preview_dir / "index.html").write_text(
        "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '  <meta charset="utf-8">',
                f'  <meta http-equiv="refresh" content="0; url={target}">',
                f'  <link rel="canonical" href="{target}">',
                "  <title>Preview redirect</title>",
                "</head>",
                "<body>",
                f'  <p><a href="{target}">Open preview</a></p>',
                "</body>",
                "</html>",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-dir", required=True)
    parser.add_argument("--url-prefix", required=True)
    parser.add_argument("--source-lang", default="en")
    args = parser.parse_args()

    preview_dir = Path(args.preview_dir).resolve()
    expose_root_assets(preview_dir, args.source_lang)
    rewrite_html_urls(preview_dir, args.url_prefix)
    write_index(preview_dir, args.url_prefix)


if __name__ == "__main__":
    main()
