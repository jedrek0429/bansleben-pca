"""Publishing helpers for generated site output."""

from __future__ import annotations

import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, CLR_WHITE, display_path, print_group, print_labeled, print_section

DEFAULT_PRESERVED_ROOT_ITEMS = ["preview", ".private", "github-webhook.php"]


def assert_safe_paths(dist: Path, dest: Path) -> None:
    if dist == dest:
        raise SystemExit("Dist and destination paths must be different.")
    if dest in dist.parents:
        raise SystemExit("Refusing to publish: dist is inside the destination. This is unsafe.")
    if dist in dest.parents:
        raise SystemExit("Refusing to publish: destination is inside dist. Choose a destination outside build output.")


def assert_assets_ok(dist: Path, root: Path, langs: list[str]) -> None:
    root_assets = dist / "assets"
    language_assets = [dist / lang / "assets" for lang in langs]
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
            *[display_path(path, root) for path in [root_assets, *language_assets] if not path.exists()],
        ],
        "ERROR",
        CLR_RED,
    )
    raise SystemExit(1)


def private_config_paths(dist: Path, langs: list[str]) -> list[Path]:
    root_private = dist / ".private" / "pca-contact-config.json"
    if root_private.exists():
        return [root_private]
    return [dist / lang / ".private" / "pca-contact-config.json" for lang in langs]


def assert_dist_ok(dist: Path, root: Path, langs: list[str], *, require_private_config: bool) -> None:
    if not dist.exists() or not dist.is_dir():
        print_group("Missing build output", [display_path(dist, root)], "ERROR", CLR_RED)
        print_labeled("ERROR", CLR_RED, "dist does not exist. Run a successful build first, then publish again.")
        raise SystemExit(1)

    required = [dist / "index.html"]
    for lang in langs:
        required.extend([dist / lang / "index.html", dist / lang / "contact.php"])

    assert_assets_ok(dist, root, langs)

    if require_private_config:
        required.extend(private_config_paths(dist, langs))

    missing = [display_path(path, root) for path in required if not path.exists()]
    if missing:
        print_group("Missing build output", missing, "ERROR", CLR_RED)
        print_labeled("ERROR", CLR_RED, "dist is incomplete. Run a successful build first, then publish again.")
        raise SystemExit(1)

    allowed_root_items = {*langs, "assets", "index.html"}
    if (dist / ".private").exists():
        allowed_root_items.add(".private")
    extra_root_items = sorted(path.name for path in dist.iterdir() if path.name not in allowed_root_items)
    if extra_root_items:
        print_group("Invalid dist root", [f"Unexpected root item: {name}" for name in extra_root_items], "ERROR", CLR_RED)
        raise SystemExit(1)


def remove_unpreserved_destination_items(dest: Path, preserved_root_items: set[str]) -> None:
    if not dest.exists():
        return
    for item in dest.iterdir():
        if item.name in preserved_root_items:
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def copy_dist_contents(dist: Path, dest: Path) -> None:
    for item in dist.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def publish(dist, dest, *, root=None, langs=None, preserve_root_item=None, require_private_config: bool = True) -> None:
    dist = Path(dist).expanduser().resolve()
    dest = Path(dest).expanduser().resolve()
    root = Path(root).expanduser().resolve() if root else dist.parent
    langs = list(langs or ["en", "fr", "hr"])
    preserved = set(preserve_root_item or DEFAULT_PRESERVED_ROOT_ITEMS)

    print_section("Publish site")
    print_labeled("FROM", CLR_WHITE, display_path(dist, root))
    print_labeled("TO", CLR_WHITE, display_path(dest, root))

    assert_safe_paths(dist, dest)
    assert_dist_ok(dist, root, langs, require_private_config=require_private_config)
    dest.mkdir(parents=True, exist_ok=True)
    remove_unpreserved_destination_items(dest, preserved)
    copy_dist_contents(dist, dest)
    print_labeled("OK", CLR_GREEN, "Publish complete.")
