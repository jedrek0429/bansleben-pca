"""
Run validation, format hyperlinks, then build and publish to v2.

Usage: run from site-src root (or specify `--root path/to/site-src`)
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate locales, build the site, then publish the v2 output."
    )
    parser.add_argument("--root", default=".", help="site-src root, default: current directory")
    args = parser.parse_args()

    validate_locales = TOOLS_DIR / "validate_locales.py"
    format_hyperlinks = TOOLS_DIR / "format_hyperlinks.py"
    build = TOOLS_DIR / "build.py"
    publish = TOOLS_DIR / "publish.py"

    for script in [validate_locales, build, publish]:
        if not script.is_file():
            print_labeled("ERROR", CLR_RED, f"Required script not found: {script}")
            sys.exit(1)
    
    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")

    if not python_bin:
        print_labeled("ERROR", CLR_RED, "Python executable not found.")
        sys.exit(1)

    steps = [
        ("Validation", [python_bin, str(validate_locales), "--root", args.root]),
        ("Format Hyperlinks", [python_bin, str(format_hyperlinks), "--root", args.root]),
        ("Build", [python_bin, str(build), "--root", args.root]),
        (
            "Publish",
            [
                python_bin,
                str(publish),
                "--dist",
                str(Path(args.root).expanduser().resolve().parent / "site-dist"),
                "--dest",
                str(Path(args.root).expanduser().resolve().parent / "public_html"),
            ],
        ),
    ]

    for label, command in steps:
        rc = subprocess.run(command)
        if rc.returncode != 0:
            print_labeled("ERROR", CLR_RED, f"{label} failed (see output).")
            sys.exit(1)

    print()
    print_labeled("OK", CLR_GREEN, "validation, hyperlinks format, build, and publish completed successfully.")


if __name__ == "__main__":
    main()
    