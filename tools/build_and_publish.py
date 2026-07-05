"""Run validation, hyperlink formatting, build, and publish for production or preview output."""

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


def empty_root_index(dist: Path) -> None:
    root_index = dist / "index.html"
    root_index.parent.mkdir(parents=True, exist_ok=True)
    root_index.write_text("", encoding="utf-8")


def write_preview_index(dest: Path, url_prefix: str) -> None:
    url_prefix = normalize_url_prefix(url_prefix)
    target = f"{url_prefix}/en/" if url_prefix else "/en/"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "index.html").write_text(
        "\n".join([
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
        ]),
        encoding="utf-8",
    )


def run_required(label: str, command: list[str]) -> None:
    rc = subprocess.run(command)
    if rc.returncode != 0:
        print_labeled("ERROR", CLR_RED, f"{label} failed (see output).")
        raise SystemExit(rc.returncode)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate, build, and publish the site.")
    parser.add_argument("--root", default=".", help="site source root")
    parser.add_argument("--dest", default=None, help="publish destination")
    parser.add_argument("--url-prefix", default="", help="optional URL prefix")
    parser.add_argument("--lang-in-url", action="store_true", help="enable language roots")
    parser.add_argument("--write-preview-index", action="store_true", help="write preview redirect index")
    parser.add_argument("--preserve-root-item", action="append", default=None, help="destination item to preserve")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    root = Path(args.root).expanduser().resolve()
    dist = root.parent / "site-dist"
    dest = Path(args.dest).expanduser().resolve() if args.dest else root.parent / "public_html"

    scripts = {
        "Validation": TOOLS_DIR / "validate_locales.py",
        "Format Hyperlinks": TOOLS_DIR / "format_hyperlinks.py",
        "Build": TOOLS_DIR / "build.py",
        "Publish": TOOLS_DIR / "publish.py",
    }

    for label, script in scripts.items():
        if not script.is_file():
            print_labeled("ERROR", CLR_RED, f"Required script not found for {label}: {script}")
            raise SystemExit(1)

    python_bin = sys.executable or shutil.which("python3") or shutil.which("python")
    if not python_bin:
        print_labeled("ERROR", CLR_RED, "Python executable not found.")
        raise SystemExit(1)

    os.environ["SITE_URL_PREFIX"] = normalize_url_prefix(args.url_prefix)
    if args.lang_in_url:
        os.environ["SITE_LANG_IN_URL"] = "1"
    else:
        os.environ.pop("SITE_LANG_IN_URL", None)

    for label, command in [
        ("Validation", [python_bin, str(scripts["Validation"]), "--root", str(root)]),
        ("Format Hyperlinks", [python_bin, str(scripts["Format Hyperlinks"]), "--root", str(root)]),
        ("Build", [python_bin, str(scripts["Build"]), "--root", str(root)]),
    ]:
        run_required(label, command)

    empty_root_index(dist)

    publish_command = [python_bin, str(scripts["Publish"]), "--dist", str(dist), "--dest", str(dest)]
    for item in args.preserve_root_item or []:
        publish_command.extend(["--preserve-root-item", item])

    run_required("Publish", publish_command)

    if args.write_preview_index:
        write_preview_index(dest, os.environ["SITE_URL_PREFIX"])

    print()
    print_labeled("OK", CLR_GREEN, "validation, build, and publish completed successfully.")


if __name__ == "__main__":
    main()
