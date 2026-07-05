"""Compatibility wrapper for publishing generated PCA build output.

Prefer:
    python tools/build.py publish ...

This script remains for existing deployment hooks.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD_PACKAGE_DIR = Path(__file__).resolve().parent / "build"
if str(BUILD_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(BUILD_PACKAGE_DIR))

from publisher import publish

DEFAULT_ROOT = Path(__file__).parents[2].resolve()
DEFAULT_PUBLIC_HTML = DEFAULT_ROOT / "public_html"
DEFAULT_DIST = DEFAULT_ROOT / "dist"
DEFAULT_DEST = DEFAULT_PUBLIC_HTML


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish generated site output.")
    parser.add_argument("--dist", default=str(DEFAULT_DIST), help="Build output directory to publish.")
    parser.add_argument("--dest", default=str(DEFAULT_DEST), help="Destination directory to publish into.")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Repository/site root for display paths.")
    parser.add_argument("--langs", default=None, help="comma-separated language list")
    parser.add_argument(
        "--preserve-root-item",
        action="append",
        dest="preserved_root_items",
        help="Root item in destination to preserve while deleting old output. Can be repeated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    langs = [part.strip() for part in args.langs.split(",") if part.strip()] if args.langs else None
    publish(
        Path(args.dist),
        Path(args.dest),
        root=Path(args.root),
        langs=langs,
        preserve_root_item=args.preserved_root_items,
    )


if __name__ == "__main__":
    main()
