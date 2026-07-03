"""
Prepare a built static site for a GitHub Pages project-site preview path.

The production site currently uses root-relative legacy WordPress/Divi asset URLs
such as /wp-content/... and /wp-includes/.... Those work on the production
domains, but a GitHub Pages project site is served below /<repo>/.

This script is preview-only. It rewrites those remaining root-relative asset URLs
inside generated HTML after a preview build that already used SITE_URL_PREFIX and
SITE_LANG_IN_URL.
"""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT_RELATIVE_PREFIXES = (
    "/wp-content/",
    "/wp-includes/",
)

HTML_ATTRS = (
    "href",
    "src",
    "srcset",
)


def normalize_prefix(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise SystemExit("--url-prefix is required")
    if not value.startswith("/"):
        value = "/" + value
    return value


def rewrite_html(text: str, prefix: str) -> str:
    for root_prefix in ROOT_RELATIVE_PREFIXES:
        replacement = prefix + root_prefix

        for attr in HTML_ATTRS:
            text = text.replace(f'{attr}="{root_prefix}', f'{attr}="{replacement}')
            text = text.replace(f"{attr}='{root_prefix}", f"{attr}='{replacement}")

        text = text.replace(f"url({root_prefix}", f"url({replacement}")
        text = text.replace(f"url('{root_prefix}", f"url('{replacement}")
        text = text.replace(f'url("{root_prefix}', f'url("{replacement}')

    return text


def write_preview_index(dist: Path, prefix: str) -> None:
    target = prefix + "/en/"
    (dist / "index.html").write_text(
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
    parser.add_argument("--dist", default="../site-dist", help="Built site directory")
    parser.add_argument("--url-prefix", required=True, help="GitHub Pages URL prefix, e.g. /repo/pr-1")
    args = parser.parse_args()

    dist = Path(args.dist).resolve()
    if not dist.exists():
        raise SystemExit(f"Built site directory does not exist: {dist}")

    prefix = normalize_prefix(args.url_prefix)

    for path in dist.rglob("*.html"):
        original = path.read_text(encoding="utf-8")
        rewritten = rewrite_html(original, prefix)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")

    write_preview_index(dist, prefix)


if __name__ == "__main__":
    main()
