#!/usr/bin/env python3
"""Regression tests for the production deployment contract."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PRESERVED_ROOT_ITEMS = ("preview", "ochronapacjenta.pl", "autoinstalator")


def run(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(root / "tools" / "build.py"), *args, "--root", str(root)]
    return subprocess.run(command, cwd=root, check=check, text=True, capture_output=True)


def prepare_source(source: Path, temp: Path) -> Path:
    root = temp / "site-src"
    shutil.copytree(
        source,
        root,
        ignore=shutil.ignore_patterns(".git", ".deploy-worktrees", "__pycache__", "site-dist"),
    )
    example = root / "pca-contact-config-example.json"
    config = json.loads(example.read_text(encoding="utf-8"))
    (root / "pca-contact-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def assert_preserved_items_survive(root: Path, destination: Path) -> None:
    sentinels: dict[str, str] = {}
    for name in PRESERVED_ROOT_ITEMS:
        path = destination / name
        path.mkdir(parents=True, exist_ok=True)
        marker = f"preserve-{name}.txt"
        payload = f"sentinel:{name}\n"
        (path / marker).write_text(payload, encoding="utf-8")
        sentinels[f"{name}/{marker}"] = payload

    run(root, "deploy", "--to", str(destination), "--no-format")

    for relative, expected in sentinels.items():
        path = destination / relative
        if not path.is_file():
            raise SystemExit(f"Production deploy removed preserved item: {relative}")
        if path.read_text(encoding="utf-8") != expected:
            raise SystemExit(f"Production deploy modified preserved item: {relative}")


def assert_failed_build_leaves_live_tree_untouched(root: Path, destination: Path) -> None:
    marker = destination / "live-before-failed-deploy.txt"
    marker.write_text("known-good\n", encoding="utf-8")
    before = marker.read_bytes()

    locale = root / "locales" / "en.json"
    original = locale.read_text(encoding="utf-8")
    locale.write_text("{ invalid json\n", encoding="utf-8")
    try:
        result = run(root, "deploy", "--to", str(destination), "--no-format", check=False)
        if result.returncode == 0:
            raise SystemExit("Deliberately invalid source unexpectedly deployed successfully")
    finally:
        locale.write_text(original, encoding="utf-8")

    if not marker.is_file() or marker.read_bytes() != before:
        raise SystemExit("Failed build changed the existing production tree")


def assert_language_layout(root: Path, destination: Path) -> None:
    manifests = {path.stem for path in (root / "sites").glob("*.json")}
    deployed = {
        path.name
        for path in destination.iterdir()
        if path.is_dir() and path.name in manifests
    }
    if deployed != manifests:
        raise SystemExit(
            f"Production language layout changed; expected={sorted(manifests)}, actual={sorted(deployed)}"
        )

    for lang in manifests:
        for relative in ("index.html", "contact.php", ".htaccess", "assets"):
            if not (destination / lang / relative).exists():
                raise SystemExit(f"Missing {lang}/{relative} after production deployment")


def main() -> None:
    source = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="pca-production-contract-") as directory:
        temp = Path(directory)
        root = prepare_source(source, temp)
        destination = temp / "public_html"

        assert_preserved_items_survive(root, destination)
        assert_language_layout(root, destination)
        assert_failed_build_leaves_live_tree_untouched(root, destination)

    print("Production deployment compatibility contract passed.")


if __name__ == "__main__":
    main()
