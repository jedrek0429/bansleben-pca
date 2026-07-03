"""Clean generated output and reject real legacy public artifacts."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, color, display_path, print_group, print_labeled, print_section

LANGS = {"en", "fr", "hr"}
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".txt", ".xml", ".svg", ".webmanifest"}
LEGACY_TERMS = (
    "wp-content",
    "wp-includes",
    "wp-admin",
    "wordpress",
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
DIVI_RE = re.compile(r"(?<![a-z0-9])divi(?![a-z0-9])", re.IGNORECASE)
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


def assert_dist_shape(dist: Path) -> None:
    root_items = {path.name for path in dist.iterdir()} if dist.exists() else set()
    extra = sorted(root_items - (LANGS | {"index.html"}))
    if extra:
        print_group("Invalid dist root", [f"Unexpected root item: {item}" for item in extra], "ERROR", CLR_RED)
        raise SystemExit(1)


def remove_legacy_paths(dist: Path) -> list[Path]:
    removed = []
    for path in sorted(dist.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        parts = [part.lower() for part in path.relative_to(dist).parts]
        remove = any(part in {"wp-admin", "wp-content", "wp-includes", "divi"} for part in parts)
        remove = remove or len(parts) >= 3 and parts[1] == "assets" and parts[2] == "common"
        if not remove:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(path)
    return removed


def sanitize_class_attr(match: re.Match[str]) -> str:
    classes = []
    for class_name in match.group(1).split():
        rewritten = CLASS_REWRITES.get(class_name, class_name)
        if rewritten and rewritten not in classes:
            classes.append(rewritten)
    return 'class="' + " ".join(classes) + '"'


def sanitize_text_files(dist: Path) -> list[Path]:
    changed = []
    for path in sorted(dist.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".htaccess":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        updated = text
        if path.suffix.lower() in {".html", ".htm"}:
            updated = re.sub(r'class="([^"]*)"', sanitize_class_attr, updated)
        if path.name == ".htaccess":
            updated = updated.replace(" https://fonts.googleapis.com", "")
            updated = updated.replace(" https://fonts.gstatic.com", "")
            updated = updated.replace("https://fonts.googleapis.com", "")
            updated = updated.replace("https://fonts.gstatic.com", "")
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)
    return changed


def legacy_in_path(path: Path, dist: Path) -> bool:
    rel = path.relative_to(dist).as_posix().lower()
    parts = rel.split("/")
    if any(part in {"wp-admin", "wp-content", "wp-includes", "divi"} for part in parts):
        return True
    return any(term in rel for term in LEGACY_TERMS if term not in {"wordpress"})


def legacy_terms(text: str) -> list[str]:
    lower = text.lower()
    leaked = [term for term in LEGACY_TERMS if term in lower]
    if DIVI_RE.search(text):
        leaked.append("divi")
    return leaked


def legacy_findings(dist: Path) -> list[str]:
    findings = []
    for path in sorted(dist.rglob("*")):
        if legacy_in_path(path, dist):
            findings.append(f"{display_path(path, dist.parent)}: legacy path")
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name != ".htaccess":
            continue
        leaked = legacy_terms(path.read_text(encoding="utf-8", errors="ignore"))
        if leaked:
            findings.append(f"{display_path(path, dist.parent)}: {', '.join(leaked)}")
    return findings


def clean_static_output(dist: Path) -> None:
    dist = dist.expanduser().resolve()
    print_section("Static Output Cleanup")
    print(color(f"Dist: {display_path(dist, dist.parent)}", CLR_GREEN))
    assert_dist_shape(dist)
    removed = remove_legacy_paths(dist)
    changed = sanitize_text_files(dist)
    if removed:
        print_group("Removed legacy paths", [display_path(path, dist.parent) for path in removed], "OK", CLR_GREEN)
    else:
        print_labeled("OK", CLR_GREEN, "no legacy directories found.")
    if changed:
        print_group("Sanitized generated text", [display_path(path, dist.parent) for path in changed], "OK", CLR_GREEN)
    findings = legacy_findings(dist)
    if findings:
        print_group("Legacy public artifacts", findings, "ERROR", CLR_RED)
        raise SystemExit(1)
    print_labeled("OK", CLR_GREEN, "public output contains no WordPress/Divi paths or references.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove and reject legacy assets from generated output.")
    parser.add_argument("--dist", required=True)
    args = parser.parse_args()
    clean_static_output(Path(args.dist))


if __name__ == "__main__":
    main()
