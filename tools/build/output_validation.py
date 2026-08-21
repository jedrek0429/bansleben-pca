"""Validation of local asset references in generated HTML."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from common import CLR_GREEN, CLR_RED, print_labeled


IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE | re.DOTALL)
SOURCE_TAG_RE = re.compile(r"<source\b[^>]*>", re.IGNORECASE | re.DOTALL)
ATTR_RE = re.compile(r"\b(?P<name>src|srcset)=[\"'](?P<value>[^\"']+)[\"']", re.IGNORECASE)


def _srcset_urls(value: str) -> list[str]:
    urls = []
    for candidate in value.split(","):
        candidate = candidate.strip()
        if candidate:
            urls.append(candidate.split(None, 1)[0])
    return urls


def _local_output_path(ctx, html_path: Path, url: str) -> Path | None:
    value = str(url or "").strip()
    if not value or value.startswith(("data:", "http://", "https://", "//", "#")):
        return None

    parsed = urlsplit(value)
    path = unquote(parsed.path)
    prefix = str(ctx.url_prefix or "").rstrip("/")
    if prefix:
        if path == prefix:
            path = "/"
        elif path.startswith(prefix + "/"):
            path = path[len(prefix):]

    if not path.startswith("/"):
        return (html_path.parent / path).resolve()

    if ctx.lang_in_url:
        return ctx.dist / path.lstrip("/")

    relative_html = html_path.relative_to(ctx.dist)
    lang = relative_html.parts[0] if relative_html.parts and relative_html.parts[0] in ctx.langs else None
    if lang:
        return ctx.dist / lang / path.lstrip("/")
    return ctx.dist / path.lstrip("/")


def validate_generated_image_references(ctx) -> None:
    """Fail a build when generated HTML advertises a missing local image file.

    This checks the actual rendered contract rather than trying to infer which
    source configuration fields may eventually become an image. It covers both
    ordinary ``src`` attributes and every candidate emitted in ``srcset``.
    """
    missing: dict[str, set[str]] = {}

    for html_path in sorted(ctx.dist.rglob("*.html")):
        text = html_path.read_text(encoding="utf-8")
        for tag in [*IMG_TAG_RE.findall(text), *SOURCE_TAG_RE.findall(text)]:
            for match in ATTR_RE.finditer(tag):
                values = _srcset_urls(match.group("value")) if match.group("name").lower() == "srcset" else [match.group("value")]
                for url in values:
                    output_path = _local_output_path(ctx, html_path, url)
                    if output_path is None or output_path.is_file():
                        continue
                    rel_html = html_path.relative_to(ctx.dist).as_posix()
                    missing.setdefault(url, set()).add(rel_html)

    if missing:
        print_labeled("ERROR", CLR_RED, "generated HTML references missing local images:")
        for url, pages in sorted(missing.items()):
            page_list = ", ".join(sorted(pages)[:4])
            suffix = " …" if len(pages) > 4 else ""
            print(f"  {url} <- {page_list}{suffix}")
        raise SystemExit(1)

    print_labeled("OK", CLR_GREEN, "generated image references resolve to build output.")
