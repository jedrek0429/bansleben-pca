"""Publishing helpers for generated site output."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from common import CLR_GREEN, CLR_RED, CLR_WHITE, display_path, print_group, print_labeled, print_section
from context import BuildContext

DEFAULT_PRESERVED_ROOT_ITEMS = ["preview", "ochronapacjenta.pl", "autoinstalator"]


def assert_safe_paths(dist: Path, dest: Path) -> None:
    if dist == dest:
        raise SystemExit("Dist and destination paths must be different.")
    if dest in dist.parents:
        raise SystemExit("Refusing to publish: dist is inside the destination. This is unsafe.")
    if dist in dest.parents:
        raise SystemExit("Refusing to publish: destination is inside dist. Choose a destination outside build output.")


def assert_shared_or_language_tree(dist: Path, root: Path, langs: list[str], name: str) -> None:
    root_path = dist / name
    language_paths = [dist / lang / name for lang in langs]
    root_exists = root_path.exists()
    language_paths_exist = all(path.exists() for path in language_paths)
    if root_exists and not language_paths_exist:
        return
    if language_paths_exist and not root_exists:
        return
    print_group(
        "Missing build output",
        [
            f"Expected either root {name}/, or {name}/ under every language directory.",
            *[display_path(path, root) for path in [root_path, *language_paths] if not path.exists()],
        ],
        "ERROR",
        CLR_RED,
    )
    raise SystemExit(1)


def assert_assets_ok(dist: Path, root: Path, langs: list[str]) -> None:
    assert_shared_or_language_tree(dist, root, langs, "assets")


def assert_generated_assets_ok(dist: Path, root: Path, langs: list[str]) -> None:
    assert_shared_or_language_tree(dist, root, langs, "_generated")


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
    assert_generated_assets_ok(dist, root, langs)

    if require_private_config:
        required.extend(private_config_paths(dist, langs))

    missing = [display_path(path, root) for path in required if not path.exists()]
    if missing:
        print_group("Missing build output", missing, "ERROR", CLR_RED)
        print_labeled("ERROR", CLR_RED, "dist is incomplete. Run a successful build first, then publish again.")
        raise SystemExit(1)

    allowed_root_items = {*langs, "assets", "_generated", "index.html"}
    if (dist / ".private").exists():
        allowed_root_items.add(".private")
    extra_root_items = sorted(path.name for path in dist.iterdir() if path.name not in allowed_root_items)
    if extra_root_items:
        print_group("Invalid dist root", [f"Unexpected root item: {name}" for name in extra_root_items], "ERROR", CLR_RED)
        raise SystemExit(1)


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def move_path(source: Path, target: Path) -> None:
    source.replace(target)


def copy_dist_contents(dist: Path, dest: Path) -> None:
    for item in dist.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)


def stage_publish(dist: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{dest.name}.pca-stage-", dir=dest.parent))
    try:
        copy_dist_contents(dist, stage)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return stage


def activate_staged_publish(stage: Path, dest: Path, preserved_root_items: set[str]) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=f".{dest.name}.pca-backup-", dir=dest.parent))
    moved_to_backup: list[str] = []
    activated: list[str] = []

    try:
        for item in list(dest.iterdir()):
            if item.name in preserved_root_items:
                continue
            move_path(item, backup / item.name)
            moved_to_backup.append(item.name)

        for item in list(stage.iterdir()):
            move_path(item, dest / item.name)
            activated.append(item.name)
    except Exception:
        for name in reversed(activated):
            remove_path(dest / name)
        for name in reversed(moved_to_backup):
            source = backup / name
            if source.exists() or source.is_symlink():
                move_path(source, dest / name)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def resolved_languages(root: Path, langs) -> list[str]:
    if langs:
        return list(langs)
    ctx = BuildContext.from_root(root)
    ctx.load_configs()
    return list(ctx.langs)


def publish(dist, dest, *, root=None, langs=None, preserve_root_item=None, require_private_config: bool = True) -> None:
    dist = Path(dist).expanduser().resolve()
    dest = Path(dest).expanduser().resolve()
    root = Path(root).expanduser().resolve() if root else dist.parent
    langs = resolved_languages(root, langs)
    preserved = set(preserve_root_item or DEFAULT_PRESERVED_ROOT_ITEMS)

    print_section("Publish site")
    print_labeled("FROM", CLR_WHITE, display_path(dist, root))
    print_labeled("TO", CLR_WHITE, display_path(dest, root))

    assert_safe_paths(dist, dest)
    assert_dist_ok(dist, root, langs, require_private_config=require_private_config)

    # Build the complete replacement tree before touching the live destination.
    # Activation uses same-filesystem renames and restores the previous tree if
    # any activation step fails. Preserved roots never move.
    stage = stage_publish(dist, dest)
    activate_staged_publish(stage, dest, preserved)
    print_labeled("OK", CLR_GREEN, "Publish complete.")
