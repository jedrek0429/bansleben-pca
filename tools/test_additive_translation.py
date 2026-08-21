#!/usr/bin/env python3
"""Regression test for adding a site without editing shared language registries."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LANG = "zz"
SITE_URL = "https://translation-contract.invalid"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(root: Path, *args: str) -> None:
    command = [sys.executable, str(root / "tools" / "build.py"), *args, "--root", str(root)]
    subprocess.run(command, cwd=root, check=True)


def expect_check_failure(root: Path, expected: str) -> None:
    command = [
        sys.executable,
        str(root / "tools" / "build.py"),
        "check",
        "--strict",
        "--no-autofix-prompt",
        "--root",
        str(root),
    ]
    result = subprocess.run(command, cwd=root, text=True, capture_output=True)
    output = result.stdout + result.stderr
    if result.returncode == 0:
        raise SystemExit(f"Expected site-model validation to fail with: {expected}")
    if expected not in output:
        raise SystemExit(f"Expected validation error {expected!r}, got:\n{output}")


def make_synthetic_locale(root: Path) -> dict:
    english = load_json(root / "locales" / "en.json")
    shared_pages = load_json(root / "config" / "pages.json").get("pages", [])
    keys = [page["key"] for page in shared_pages]

    locale = dict(english)
    locale["lang"] = LANG
    locale["site_name"] = "Synthetic Translation"
    locale.pop("domain", None)
    locale["pages"] = {
        key: {
            "enabled": True,
            "title": "Synthetic Translation" if key == "introduction" else f"Synthetic {key.replace('_', ' ')}",
            "slug": "" if key == "introduction" else f"zz-{key.replace('_', '-')}",
        }
        for key in keys
    }
    locale["seo"] = {
        "default_description": "Synthetic description used by the additive translation contract test.",
        "descriptions": {key: f"Synthetic SEO description for {key}." for key in keys},
    }
    return locale


def main() -> None:
    source = Path(__file__).resolve().parents[1]
    shared_seo = load_json(source / "config" / "seo.json")
    serialized_seo = json.dumps(shared_seo, ensure_ascii=False)
    if f'"{LANG}"' in serialized_seo:
        raise SystemExit(f"Synthetic language {LANG!r} must not be registered in config/seo.json")

    with tempfile.TemporaryDirectory(prefix="pca-additive-translation-") as temp:
        root = Path(temp) / "site-src"
        shutil.copytree(
            source,
            root,
            ignore=shutil.ignore_patterns(".git", ".deploy-worktrees", "__pycache__", "site-dist"),
        )

        sites_dir = root / "sites"
        for path in sites_dir.glob("*.json"):
            path.unlink()
        site_path = sites_dir / f"{LANG}.json"
        site_manifest = {
            "url": SITE_URL,
            "hreflang": LANG,
            "og_locale": "zz_ZZ",
            "social_image": "/assets/social/og-en.jpg",
            "extra_pages": [],
        }
        write_json(site_path, site_manifest)

        locale_dir = root / "locales"
        synthetic = make_synthetic_locale(root)
        for path in locale_dir.glob("*.json"):
            path.unlink()
        write_json(locale_dir / f"{LANG}.json", synthetic)

        content_dir = root / "content" / LANG
        content_dir.mkdir(parents=True, exist_ok=True)
        shared_keys = set(synthetic["pages"])
        for path in (root / "content" / "en").glob("*.md"):
            if path.stem in shared_keys:
                shutil.copy2(path, content_dir / path.name)

        run(root, "check", "--strict", "--no-autofix-prompt")

        for field in ("url", "hreflang", "og_locale", "social_image"):
            incomplete_site = dict(site_manifest)
            incomplete_site.pop(field)
            write_json(site_path, incomplete_site)
            expect_check_failure(root, f"Site '{LANG}' missing required {field}")
        write_json(site_path, site_manifest)

        invalid_site = dict(site_manifest)
        invalid_site["url"] = "/not-an-absolute-site-url"
        write_json(site_path, invalid_site)
        expect_check_failure(root, f"Site '{LANG}' url must be an absolute HTTP(S) URL")
        write_json(site_path, site_manifest)

        incomplete_locale = dict(synthetic)
        incomplete_locale.pop("seo")
        write_json(locale_dir / f"{LANG}.json", incomplete_locale)
        expect_check_failure(root, f"Locale '{LANG}' missing seo object")

        incomplete_locale = dict(synthetic)
        incomplete_locale["seo"] = dict(synthetic["seo"])
        incomplete_locale["seo"].pop("default_description")
        write_json(locale_dir / f"{LANG}.json", incomplete_locale)
        expect_check_failure(root, f"Locale '{LANG}' seo.default_description is required")

        incomplete_locale = dict(synthetic)
        incomplete_locale["seo"] = dict(synthetic["seo"])
        incomplete_locale["seo"]["descriptions"] = dict(synthetic["seo"]["descriptions"])
        incomplete_locale["seo"]["descriptions"].pop("whom_to_contact")
        write_json(locale_dir / f"{LANG}.json", incomplete_locale)
        expect_check_failure(root, f"Locale '{LANG}' seo.descriptions.whom_to_contact is required")
        write_json(locale_dir / f"{LANG}.json", synthetic)

        missing_content = content_dir / "whom_to_contact.md"
        parked_content = content_dir / "whom_to_contact.md.missing"
        missing_content.rename(parked_content)
        expect_check_failure(root, f"Locale '{LANG}' missing content/{LANG}/whom_to_contact.md")
        parked_content.rename(missing_content)

        content_text = missing_content.read_text(encoding="utf-8")
        missing_content.write_text("\n", encoding="utf-8")
        expect_check_failure(root, f"Locale '{LANG}' content/{LANG}/whom_to_contact.md is empty")
        missing_content.write_text(content_text, encoding="utf-8")

        run(root, "check", "--strict", "--no-autofix-prompt")
        output = root.parent / "contract-dist"
        run(root, "site", "--out", str(output), "--langs", LANG)

        html_files = list(output.rglob("*.html"))
        if not html_files:
            raise SystemExit("Synthetic translation build produced no HTML")
        rendered = "\n".join(path.read_text(encoding="utf-8") for path in html_files)
        if SITE_URL not in rendered:
            raise SystemExit("Synthetic site URL was not sourced from sites/zz.json")
        if 'hreflang="zz"' not in rendered:
            raise SystemExit("Synthetic hreflang was not sourced from sites/zz.json")
        if "Synthetic SEO description" not in rendered:
            raise SystemExit("Synthetic SEO descriptions were not sourced from locales/zz.json")

        preview_output = root.parent / "contract-preview"
        run(root, "preview", "--to", str(preview_output), "--prefix", "contract", "--no-format")
        preview_index = preview_output / LANG / "index.html"
        if not preview_index.is_file():
            raise SystemExit(
                "Manifest-discovered preview omitted the synthetic locale; preview/deploy must not use a hard-coded language list"
            )
        preview_html = preview_index.read_text(encoding="utf-8")
        if ">ZZ</a>" not in preview_html:
            raise SystemExit("Manifest-discovered preview omitted the synthetic locale from the language switcher")

    print("Additive translation contract passed.")


if __name__ == "__main__":
    main()
