"""Expose shared language assets at a GitHub Pages preview root.

The static build publishes assets inside each language directory. GitHub Pages PR
screenshots serve the generated site from a preview root, so this helper exposes
only the current PCA asset directory at that root.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT_ITEMS = ("assets",)


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-dir", required=True)
    parser.add_argument("--source-lang", default="en")
    args = parser.parse_args()

    preview_dir = Path(args.preview_dir).resolve()
    source_dir = preview_dir / args.source_lang

    if not source_dir.is_dir():
        raise SystemExit(f"Missing preview source language directory: {source_dir}")

    for item in ROOT_ITEMS:
        copy_item(source_dir / item, preview_dir / item)


if __name__ == "__main__":
    main()
