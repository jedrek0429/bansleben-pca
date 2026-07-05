"""Command-line interface for the PCA static site builder."""

from __future__ import annotations

import argparse
from pathlib import Path

from builder import build

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build PCA static site.")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build(args.root)


if __name__ == "__main__":
    main()
