"""Compatibility wrapper for the PCA builder deploy workflow.

Prefer:
    python tools/build.py deploy ...

This script remains for existing deployment hooks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD_PACKAGE_DIR = Path(__file__).resolve().parent / "build"
if str(BUILD_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(BUILD_PACKAGE_DIR))

from workflow import deploy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate, build, and publish the site.")
    parser.add_argument("--root", default=".", help="site source root")
    parser.add_argument("--dest", default=None, help="publish destination")
    parser.add_argument("--url-prefix", default="", help="optional URL prefix")
    parser.add_argument("--lang-in-url", action="store_true", help="enable language roots")
    parser.add_argument("--write-preview-index", action="store_true", help="write preview redirect index")
    parser.add_argument("--preserve-root-item", action="append", default=None, help="destination item to preserve")
    parser.add_argument("--langs", default=None, help="comma-separated language list")
    parser.add_argument("--skip-webp", action="store_true", help="skip ImageMagick WebP conversion")
    parser.add_argument("--no-format", action="store_true", help="skip hyperlink formatting step")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    deploy(
        args.root,
        dest=args.dest,
        url_prefix=args.url_prefix,
        lang_in_url=args.lang_in_url,
        write_preview_index_flag=args.write_preview_index,
        preserve_root_item=args.preserve_root_item,
        langs=args.langs,
        skip_webp=args.skip_webp,
        no_format=args.no_format,
    )


if __name__ == "__main__":
    main()
