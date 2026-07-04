"""
Publishes the contents of dist to public_html, or a specified destination.

Expected dist layout:
    dist/
        index.html        # empty
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
        DIST / "en" / "assets",
        DIST / "fr" / "assets",
        DIST / "hr" / "assets",
        DIST / "en" / "contact.php",
        DIST / "fr" / "contact.php",
        DIST / "hr" / "contact.php",
    ]

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

    allowed_root_items = {*LANGS, "index.html"}
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
            "dist root may contain only: index.html, en, fr, hr.",
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


def publish_dist() -> str:
    if DEST is None:
        raise SystemExit("Missing required destination path.")

    assert_safe_paths()

    DEST.mkdir(parents=True, exist_ok=True)

    if shutil.which("rsync"):
        subprocess.run(
            [
                "rsync",
                "-a",
                "--delete",
                *rsync_exclude_args(),
                str(DIST) + "/",
                str(DEST) + "/",
            ],
            check=True,
        )
        return "rsync"

    remove_unpreserved_destination_items()
    copy_dist_contents()
    return "copytree"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish a built dist directory to a destination directory."
    )
    parser.add_argument(
        "--dist",
        default=str(DEFAULT_DIST),
        help=f"built dist directory to publish (default: {DEFAULT_DIST})",
    )
    parser.add_argument(
        "--dest",
        default=str(DEFAULT_DEST),
        help=f"destination directory to publish into (default: {DEFAULT_DEST})",
    )
    parser.add_argument(
        "--preserve-root-item",
        action="append",
        default=DEFAULT_PRESERVED_ROOT_ITEMS,
        help=(
            "root-level destination item to preserve during --delete publishing. "
            "May be passed multiple times. Defaults to preserving preview, .private, and github-webhook.php."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(Path(args.dist), Path(args.dest), args.preserve_root_item)

    print_section("Site Publish Report")
    print(color(f"Source:      {display_path(DIST, ROOT)}", CLR_WHITE))
    print(color(f"Destination: {display_path(DEST, ROOT)}", CLR_WHITE))
    if PRESERVED_ROOT_ITEMS:
        preserved = ", ".join(sorted(PRESERVED_ROOT_ITEMS))
        print(color(f"Preserving:  {preserved}", CLR_WHITE))

    assert_dist_ok()

    method = publish_dist()

    print_labeled("OK", CLR_GREEN, f"published site using {method}.")
    print_labeled("OK", CLR_GREEN, f"destination: {display_path(DEST, ROOT)}")


if __name__ == "__main__":
    main()
