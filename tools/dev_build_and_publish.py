"""Backward-compatible preview wrapper for tools/build_and_publish.py."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BUILD_AND_PUBLISH = Path(__file__).resolve().with_name("build_and_publish.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish development or preview output using the shared build pipeline."
    )
    parser.add_argument("--root", default=".", help="site source root, default: current directory")
    parser.add_argument("--url-prefix", default="/v2", help="URL prefix for the development build")
    parser.add_argument("--dest", default=None, help="publish destination")
    parser.add_argument("--write-preview-index", action="store_true", help="write preview redirect index")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    dest = Path(args.dest).expanduser().resolve() if args.dest else root.parent / "public_html" / "en/v2"

    command = [
        sys.executable,
        str(BUILD_AND_PUBLISH),
        "--root",
        str(root),
        "--dest",
        str(dest),
        "--url-prefix",
        args.url_prefix,
        "--lang-in-url",
    ]

    if args.write_preview_index:
        command.append("--write-preview-index")

    raise SystemExit(subprocess.run(command).returncode)


if __name__ == "__main__":
    main()
