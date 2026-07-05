"""
Publishes the contents of dist to public_html, or a specified destination.

Expected dist layout for production:
    dist/
        index.html        # empty
        en/
            .private/pca-contact-config.json
        fr/
            .private/pca-contact-config.json
        hr/
            .private/pca-contact-config.json

Expected dist layout for previews:
    dist/
        index.html        # with redirect
        assets/
        en/
        fr/
        hr/

Example:
    python publish.py --dist /path/to/dist --dest /path/to/public_html
"""

import argparse
import subprocess
import shutil
from pathlib import Path

from common import (
    CLR_GREEN,
    CLR_RED,
    CLR_WHITE,
    color,
    display_path,
    print_group,
    print_labeled,
    print_section,
)


DEFAULT_ROOT = Path(__file__).parents[2].resolve()
DEFAULT_PUBLIC_HTML = DEFAULT_ROOT / "public_html"
DEFAULT_DIST = DEFAULT_ROOT / "dist"
DEFAULT_DEST = DEFAULT_PUBLIC_HTML

ROOT = DEFAULT_ROOT
PUBLIC_HTML = DEFAULT_PUBLIC_HTML
DIST = DEFAULT_DIST
DEST = DEFAULT_DEST

LANGS = ["en", "fr", "hr"]
DEFAULT_PRESERVED_ROOT_ITEMS = ["preview", ".private", "github-webhook.php"]
PRESERVED_ROOT_ITEMS = set(DEFAULT_PRESERVED_ROOT_ITEMS)


def configure_paths(dist: Path, dest: Path, preserved_root_items: list[str] | None = None) -> None:
    global DIST, DEST, ROOT, PUBLIC_HTML, PRESERVED_ROOT_ITEMS

    DIST = Path(dist).expanduser().resolve()
    DEST = Path(dest).expanduser().resolve()

    ROOT = DEFAULT_ROOT
    PUBLIC_HTML = DEFAULT_PUBLIC_HTML
    PRESERVED_ROOT_ITEMS = set(preserved_root_items or DEFAULT_PRESERVED_ROOT_ITEMS)


def assert_safe_paths() -> None:
    if DIST == DEST:
        raise SystemExit("Dist and destination paths must be different.")

    if DEST in DIST.parents:
        raise SystemExit(
            "Refusing to publish: dist is inside the destination. "
            "This is unsafe with --delete publishing."
        )

    if DIST in DEST.parents:
        raise SystemExit(
            "Refusing to publish: destination is inside dist. "
            "Choose a destination outside the build output."
        )


def dist_uses_root_assets() -> bool:
    return (DIST / "assets").exists()


def assert_assets_ok() -> None:
    root_assets = DIST / "assets"
    language_assets = [DIST / lang / "assets" for lang in LANGS]

    root_assets_exist = root_assets.exists()
    language_assets_exist = all(path.exists() for path in language_assets)

    if root_assets_exist and not language_assets_exist:
        return

    if language_assets_exist and not root_assets_exist:
        return

    print_group(
        "Missing build output",
        [
            "Expected either root assets/, or assets/ under every language directory.",
            *[display_path(path, ROOT) for path in [root_assets, *language_assets] if not path.exists()],
        ],
        "ERROR",
        CLR_RED,
    )
    raise SystemExit(1)


def assert_dist_ok() -> None:
    if not DIST.exists() or not DIST.is_dir():
        print_group(
            "Missing build output",
            [display_path(DIST, ROOT)],
            "ERROR",
            CLR_RED,
        )
        print_labeled(
            "ERROR",
            CLR_RED,
            "dist does not exist. Run a successful build first, then publish again.",
        )
        raise SystemExit(1)

    required = [
        DIST / "index.html",
        DIST / "en" / "index.html",
        DIST / "fr" / "index.html",
        DIST / "hr" / "index.html",
        DIST / "en" / "contact.php",
        DIST / "fr" / "contact.php",
        DIST / "hr" / "contact.php",
    ]

    assert_assets_ok()

    if not dist_uses_root_assets():
        required.extend(
            DIST / lang / ".private" / "pca-contact-config.json"
            for lang in LANGS
        )

    missing = [display_path(p, ROOT) for p in required if not p.exists()]

    if missing:
        print_group("Missing build output", missing, "ERROR", CLR_RED)
        print_labeled(
            "ERROR",
            CLR_RED,
            "dist is incomplete. Run a successful build first, then publish again.",
        )
        raise SystemExit(1)

    root_index = DIST / "index.html"
    if root_index.read_text(encoding="utf-8") != "":
        print_group(
            "Invalid dist root",
            [f"{display_path(root_index, ROOT)} must be empty."],
            "ERROR",
            CLR_RED,
        )
        raise SystemExit(1)

    allowed_root_items = {*LANGS, "assets", "index.html"}
    if (DIST / ".private").exists():
        # Private config can exist in production-like build environments, but
        # preview builds do not have contact config and must not require it.
        allowed_root_items.add(".private")

    extra_root_items = sorted(
        path.name for path in DIST.iterdir()
        if path.name not in allowed_root_items
    )

    if extra_root_items:
        print_group(
            "Invalid dist root",
            [f"Unexpected root item: {name}" for name in extra_root_items],
            "ERROR",
            CLR_RED,
        )
        print_labeled(
            "ERROR",
            CLR_RED,
            "dist root may contain only: index.html, optional assets, optional .private, en, fr, hr.",
        )
        raise SystemExit(1)


def rsync_exclude_args() -> list[str]:
    args = []
    for name in sorted(PRESERVED_ROOT_ITEMS):
        if name:
            args.extend(["--exclude", f"/{name}", "--exclude", f"/{name}/"])
    return args


def remove_unpreserved_destination_items() -> None:
    if not DEST.exists():
        return

    for item in DEST.iterdir():
        if item.name in PRESERVED_ROOT_ITEMS:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def copy_dist_contents() -> None:
    for item in DIST.iterdir():
        target = DEST / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def publish() -> None:
    print_section("Publish site")
    print_labeled("FROM", CLR_WHITE, display_path(DIST, ROOT))
    print_labeled("TO", CLR_WHITE, display_path(DEST, ROOT))

    assert_safe_paths()
    assert_dist_ok()

    DEST.mkdir(parents=True, exist_ok=True)

    remove_unpreserved_destination_items()
    copy_dist_contents()

    print_labeled("OK", CLR_GREEN, "Publish complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", default=str(DEFAULT_DIST), help="Build output directory to publish.")
    parser.add_argument("--dest", default=str(DEFAULT_DEST), help="Destination directory to publish into.")
    parser.add_argument(
        "--preserve-root-item",
        action="append",
        dest="preserved_root_items",
        help="Root item in destination to preserve while deleting old output. Can be repeated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(Path(args.dist), Path(args.dest), args.preserved_root_items)
    publish()


if __name__ == "__main__":
    main()
