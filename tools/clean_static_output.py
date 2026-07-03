"""Remove and reject legacy WordPress/Divi artifacts from generated public output."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, color, display_path, print_group, print_labeled, print_section

LEGACY_TERMS = (
    "wp-content",
    "wp-includes",
    "wp-admin",
    "wordpress",
    "divi",
    "et_pb",
    "et-core",
    "et_first_mobile_item",
    "wp-image",
    "menu-item-type-post_type",
    "menu-item-object-page",
    "current_page_item",
    "page_item",
    "elegantthemes",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
)
CLASS_REWRITES = {
    "menu-item": "nav-item",
    "menu-item-type-post_type": "",
    "menu-item-object-page": "",
    "menu-item-type-custom": "",
    "menu-item-object-custom": "",
    "menu-item-home": "nav-item--home",
    "current-menu-item": "is-current",
    "page_item": "",
    "current_page_item": "is-current",
    "et_first_mobile_item": "nav-item--first-mobile",
}
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".txt", ".xml", ".svg", ".webmanifest"}
LANGS = {"en", "fr", "hr"}


def remove_legacy_paths(dist: Path) -> list[Path]:
    removed: list[Path] = []

    for path in sorted(dist.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue

        rel_parts = path.relative_to(dist).parts
        lower_parts = [part.lower() for part in rel_parts]

        should_remove = any(part in {"wp-admin", "wp-content", "wp-includes"} for part in lower_parts)
        should_remove = should_remove or len(lower_parts) >= 3 and lower_parts[1] == "assets" and lower_parts[2] == "common"

        if not should_remove:
            continue

        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)

    return removed


def sanitize_class_attribute(match: re.Match[str]) -> str:
    classes: list[str] = []

    for class_name in match.group(1).split():
        rewritten = CLASS_REWRITES.get(class_name, class_name)
        if not rewritten:
            continue
        if rewritten not in classes:
            classes.append(rewritten)

    return 'class="' + " ".join(classes) + '"'


def sanitize_generated_html(dist: Path) -> list[Path]:
    changed: list[Path] = []

    for path in sorted(dist.rglob("*.html")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = re.sub(r'class="([^"]*)"', sanitize_class_attribute, text)

        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)

    return changed


def legacy_findings(dist: Path) -> list[str]:
    findings: list[str] = []

    for path in sorted(dist.rglob("*")):
        rel = path.relative_to(dist).as_posix().lower()

        if any(term in rel for term in LEGACY_TERMS):
            findings.append(f"{display_path(path, dist.parent)}: legacy path")
            continue

        if not path.is_file():
            continue

        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".htaccess":
            continue

        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        leaked = [term for term in LEGACY_TERMS if term in text]
        if leaked:
            findings.append(f"{display_path(path, dist.parent)}: {', '.join(leaked)}")

    return findings


def assert_dist_shape(dist: Path) -> None:
    if not dist.exists() or not dist.is_dir():
        raise SystemExit(f"Missing dist directory: {dist}")

    root_items = {path.name for path in dist.iterdir()}
    expected = LANGS | {"index.html"}
    extra = sorted(root_items - expected)

    if extra:
        print_group("Invalid dist root", [f"Unexpected root item: {item}" for item in extra], "ERROR", CLR_RED)
        raise SystemExit(1)


def clean_static_output(dist: Path) -> None:
    dist = dist.expanduser().resolve()

    print_section("Static Output Cleanup")
    print(color(f"Dist: {display_path(dist, dist.parent)}", CLR_GREEN))

    assert_dist_shape(dist)
    removed = remove_legacy_paths(dist)
    rewritten = sanitize_generated_html(dist)

    if removed:
        print_group("Removed legacy paths", [display_path(path, dist.parent) for path in removed], "OK", CLR_GREEN)
    else:
        print_labeled("OK", CLR_GREEN, "no legacy directories found.")

    if rewritten:
        print_group("Sanitized generated markup", [display_path(path, dist.parent) for path in rewritten], "OK", CLR_GREEN)

    findings = legacy_findings(dist)
    if findings:
        print_group("Legacy public artifacts", findings, "ERROR", CLR_RED)
        raise SystemExit(1)

    print_labeled("OK", CLR_GREEN, "public output contains no WordPress/Divi paths or references.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove and reject legacy assets from generated static output.")
    parser.add_argument("--dist", required=True, help="built site-dist directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_static_output(Path(args.dist))


if __name__ == "__main__":
    main()
