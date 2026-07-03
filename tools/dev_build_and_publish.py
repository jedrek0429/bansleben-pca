"""
Run validation, hyperlink formatting, build, and publish a development/preview site.

Usage: run from site source root, or specify `--root path/to/site-src`.

Example:
    python tools/dev_build_and_publish.py \
      --url-prefix /bansleben-pca/pr-1 \
      --dest pages-preview/pr-1 \
      --write-preview-index
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from common import CLR_GREEN, CLR_RED, print_labeled


TOOLS_DIR = Path(__file__).resolve().parent


def normalize_url_prefix(value: str) -> str:
    value = str(value or "").strip().rstrip("/")
    if not value:
        return ""
    if not value.startswith("/"):
        value = "/" + value
    return value


def write_preview_index(dist: Path, url_prefix: str) -> None:
    """Write a root index.html that redirects to the English preview root."""
    url_prefix = normalize_url_prefix(url_prefix)
    target = f"{url_prefix}/en/" if url_prefix else "/en/"
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
    parser = argparse.ArgumentParser(
        description="Validate locales, format hyperlinks, build the site, then publish development output."
    )
    parser.add_argument("--root", default=".", help="site source root, default: current directory")
    parser.add_argument(
        "--url-prefix",
        default="/v2",
        help="URL prefix for the development build, default: /v2",
    )
    parser.add_argument(
        "--dest",
        default=None,
        help="Publish destination, default: ../public_html/en/v2 relative to root",
    )
    parser.add_argument(
        "--write-preview-index",
        action="store_true",
        help="Write a root index.html redirecting to the English preview root.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    dist = root.parent / "site-dist"
    dest = Path(args.dest).expanduser().resolve() if args.dest else root.parent / "public_html" / "en/v2"

    validate_locales = TOOLS_DIR / "validate_locales.py"
    format_hyperlinks = TOOLS_DIR / "format_hyperlinks.py"
    build = TOOLS_DIR / "build.py"
    publish = TOOLS_DIR / "publish.py"

    for script in [validate_locales, format_hyperlinks, build, publish]:
        if not script.is_file():
            print_labeled("ERROR", CLR_RED, f"Required script not found: {script}")
            sys.exit(1)

    os.environ["SITE_URL_PREFIX"] = normalize_url_prefix(args.url_prefix)
    os.environ["SITE_LANG_IN_URL"] = "1"

    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")

    if not python_bin:
        print_labeled("ERROR", CLR_RED, "Python executable not found.")
        sys.exit(1)

    steps = [
        ("Validation", [python_bin, str(validate_locales), "--root", str(root)]),
        ("Format Hyperlinks", [python_bin, str(format_hyperlinks), "--root", str(root)]),
        ("Build", [python_bin, str(build), "--root", str(root)]),
    ]

    for label, command in steps:
        rc = subprocess.run(command)
        if rc.returncode != 0:
            print_labeled("ERROR", CLR_RED, f"{label} failed (see output).")
            sys.exit(1)

    if args.write_preview_index:
        write_preview_index(dist, os.environ["SITE_URL_PREFIX"])

    rc = subprocess.run(
        [
            python_bin,
            str(publish),
            "--dist",
            str(dist),
            "--dest",
            str(dest),
        ]
    )
    if rc.returncode != 0:
        print_labeled("ERROR", CLR_RED, "Publish failed (see output).")
        sys.exit(1)

    print()
    print_labeled("OK", CLR_GREEN, "validation, hyperlink formatting, build, and publish completed successfully.")


if __name__ == "__main__":
    main()
