"""
Run validation, format hyperlinks, then build, clean and publish to v2.

Usage: run from site-src root (or specify `--root path/to/site-src`)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from common import CLR_GREEN, CLR_RED, print_labeled


TOOLS_DIR = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate locales, build the site, clean public output, then publish the v2 output."
    )
    parser.add_argument("--root", default=".", help="site-src root, default: current directory")
    args = parser.parse_args()

    validate_locales = TOOLS_DIR / "validate_locales.py"
    format_hyperlinks = TOOLS_DIR / "format_hyperlinks.py"
    build = TOOLS_DIR / "build.py"
    static_output_guard = TOOLS_DIR / "clean_static_output_v2.py"
    publish = TOOLS_DIR / "publish.py"

    for script in [validate_locales, build, static_output_guard, publish]:
        if not script.is_file():
            print_labeled("ERROR", CLR_RED, f"Required script not found: {script}")
            sys.exit(1)

    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")

    if not python_bin:
        print_labeled("ERROR", CLR_RED, "Python executable not found.")
        sys.exit(1)

    root = Path(args.root).expanduser().resolve()
    dist = root.parent / "site-dist"
    dest = root.parent / "public_html"

    steps = [
        ("Validation", [python_bin, str(validate_locales), "--root", str(root)]),
        ("Format Hyperlinks", [python_bin, str(format_hyperlinks), "--root", str(root)]),
        ("Build", [python_bin, str(build), "--root", str(root)]),
        ("Static Output Guard", [python_bin, str(static_output_guard), "--dist", str(dist)]),
        (
            "Publish",
            [
                python_bin,
                str(publish),
                "--dist",
                str(dist),
                "--dest",
                str(dest),
            ],
        ),
    ]

    for label, command in steps:
        rc = subprocess.run(command)
        if rc.returncode != 0:
            print_labeled("ERROR", CLR_RED, f"{label} failed (see output).")
            sys.exit(1)

    print()
    print_labeled("OK", CLR_GREEN, "validation, hyperlinks format, build, static output guard, and publish completed successfully.")


if __name__ == "__main__":
    main()
