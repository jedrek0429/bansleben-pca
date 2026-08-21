#!/usr/bin/env python3
"""Regression test for serving every production site from its own webroot."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(root: Path, *args: str) -> None:
    command = [sys.executable, str(root / "tools" / "build.py"), *args, "--root", str(root)]
    subprocess.run(command, cwd=root, check=True)


def require(path: Path, description: str) -> None:
    if not path.exists():
        raise SystemExit(f"Missing {description}: {path}")


def site_manifests(root: Path) -> dict[str, dict]:
    manifests = {}
    for path in sorted((root / "sites").glob("*.json")):
        manifests[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    if not manifests:
        raise SystemExit("No site manifests found")
    return manifests


def verify_language_root(destination: Path, lang: str, manifest: dict) -> None:
    language_root = destination / lang
    for relative, description in (
        ("index.html", "index"),
        ("assets", "assets directory"),
        ("contact.php", "contact handler"),
        (".htaccess", "Apache configuration"),
        (".private/pca-contact-config.json", "private contact configuration"),
        ("sitemap.xml", "sitemap"),
        ("robots.txt", "robots file"),
        ("site.webmanifest", "web app manifest"),
    ):
        require(language_root / relative, f"{lang} {description}")

    html = (language_root / "index.html").read_text(encoding="utf-8")
    expected_domain = str(manifest.get("url") or "").rstrip("/")
    if not expected_domain:
        raise SystemExit(f"Site manifest {lang!r} has no production URL")
    if expected_domain not in html:
        raise SystemExit(f"{lang} production HTML does not use its manifest domain {expected_domain}")
    if 'href="/assets/' not in html and 'src="/assets/' not in html:
        raise SystemExit(f"{lang} production HTML does not use root-relative assets")
    if f'href="/{lang}/' in html or f'src="/{lang}/' in html:
        raise SystemExit(f"{lang} production HTML incorrectly requires a /{lang}/ URL prefix")

    robots = (language_root / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {expected_domain}/sitemap.xml" not in robots:
        raise SystemExit(f"{lang} robots.txt does not use its manifest domain")

    sitemap = (language_root / "sitemap.xml").read_text(encoding="utf-8")
    if expected_domain not in sitemap:
        raise SystemExit(f"{lang} sitemap does not use its manifest domain")


def main() -> None:
    source = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(prefix="pca-production-webroots-") as temp:
        root = Path(temp) / "site-src"
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

        manifests = site_manifests(root)
        destination = root.parent / "public_html"
        run(root, "deploy", "--to", str(destination), "--no-format")

        deployed_languages = {path.name for path in destination.iterdir() if path.is_dir() and path.name in manifests}
        if deployed_languages != set(manifests):
            missing = sorted(set(manifests) - deployed_languages)
            extra = sorted(deployed_languages - set(manifests))
            raise SystemExit(f"Production deployment language mismatch; missing={missing}, extra={extra}")

        for lang, manifest in manifests.items():
            verify_language_root(destination, lang, manifest)

        root_index = (destination / "index.html").read_text(encoding="utf-8")
        if root_index:
            raise SystemExit("Production root index should remain empty; site domains must point at language directories")

    print("Production language webroot contract passed for: " + ", ".join(manifests))


if __name__ == "__main__":
    main()
