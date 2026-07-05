from __future__ import annotations

import argparse
import sys
from pathlib import Path

BUILD_PACKAGE_DIR = Path(__file__).resolve().parent / "build"
if str(BUILD_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(BUILD_PACKAGE_DIR))

from workflow import deploy, preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route deployment hooks into the PCA builder app.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--dest", default=None)
    parser.add_argument("--url-prefix", default="")
    parser.add_argument("--lang-in-url", action="store_true")
    parser.add_argument("--write-preview-index", action="store_true")
    parser.add_argument("--preserve-root-item", action="append", default=None)
    parser.add_argument("--langs", default=None)
    parser.add_argument("--skip-webp", action="store_true")
    parser.add_argument("--no-format", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    is_preview = bool(args.url_prefix or args.lang_in_url or args.write_preview_index)
    if is_preview:
        preview(args.root, prefix=args.url_prefix, to=args.dest, langs=args.langs, clean_content=not args.no_format)
    else:
        deploy(args.root, to=args.dest, langs=args.langs, clean_content=not args.no_format)


if __name__ == "__main__":
    main()
