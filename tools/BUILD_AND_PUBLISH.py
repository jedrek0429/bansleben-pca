"""Run validation, hyperlink formatting, build, and publish for the static site."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from common import CLR_GREEN, CLR_RED, print_labeled


TOOLS_DIR = Path(__file__).resolve().parent


def empty_root_index(dist: Path) -> None:
    """Keep the generated public root index compatible with publish.py."""
    root_index = dist / "index.html"
    root_index.parent.mkdir(parents=True, exist_ok=True)
    root_index.write_text("", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate locales, format hyperlinks, build the site, then publish the output."
    )
    parser.add_argument("--root", default=".", help="site source root, default: current directory")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    dist = root.parent / "site-dist"
    dest = root.parent / "public_html"

    scripts = {
        "Validation": TOOLS_DIR / "validate_locales.py",
        "Format Hyperlinks": TOOLS_DIR / "format_hyperlinks.py",
        "Build": TOOLS_DIR / "build.py",
        "Publish": TOOLS_DIR / "publish.py",
    }

    for label, script in scripts.items():
        if not script.is_file():
            print_labeled("ERROR", CLR_RED, f"Required script not found for {label}: {script}")
            sys.exit(1)

    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")

    if not python_bin:
        print_labeled("ERROR", CLR_RED, "Python executable not found.")
        sys.exit(1)

    build_steps = [
        ("Validation", [python_bin, str(scripts["Validation"]), "--root", str(root)]),
        ("Format Hyperlinks", [python_bin, str(scripts["Format Hyperlinks"]), "--root", str(root)]),
        ("Build", [python_bin, str(scripts["Build"]), "--root", str(root)]),
    ]

    for label, command in build_steps:
        rc = subprocess.run(command)
        if rc.returncode != 0:
            print_labeled("ERROR", CLR_RED, f"{label} failed (see output).")
            sys.exit(1)

    empty_root_index(dist)

    publish_command = [
        python_bin,
        str(scripts["Publish"]),
        "--dist",
        str(dist),
        "--dest",
        str(dest),
    ]

    rc = subprocess.run(publish_command)
    if rc.returncode != 0:
        print_labeled("ERROR", CLR_RED, "Publish failed (see output).")
        sys.exit(1)

    print()
    print_labeled("OK", CLR_GREEN, "validation, hyperlink formatting, build, and publish completed successfully.")


if __name__ == "__main__":
    main()
