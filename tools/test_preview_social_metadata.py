#!/usr/bin/env python3
"""Regression test for absolute metadata URLs in path-scoped PR previews."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    source = Path(__file__).resolve().parents[1]
    prefix = "pr-999"

    with tempfile.TemporaryDirectory(prefix="pca-preview-metadata-") as temp:
        root = Path(temp) / "site-src"
        destination = Path(temp) / "preview" / prefix
        shutil.copytree(
            source,
            root,
            ignore=shutil.ignore_patterns(".git", ".deploy-worktrees", "__pycache__", "site-dist"),
        )

        subprocess.run(
            [
                sys.executable,
                str(root / "tools" / "build.py"),
                "preview",
                "--root",
                str(root),
                "--prefix",
                prefix,
                "--to",
                str(destination),
                "--no-format",
            ],
            cwd=root,
            check=True,
        )

        seo = json.loads((root / "config" / "seo.json").read_text(encoding="utf-8"))
        site = json.loads((root / "sites" / "pl.json").read_text(encoding="utf-8"))
        base = str(seo["preview_site_url"]).rstrip("/")
        social_image = str(site["social_image"])
        expected_image = f"{base}/{prefix}{social_image}"
        expected_page = f"{base}/{prefix}/pl/"

        html = (destination / "pl" / "index.html").read_text(encoding="utf-8")
        required = [
            f'<link rel="canonical" href="{expected_page}">',
            f'<meta property="og:url" content="{expected_page}">',
            f'<meta property="og:image" content="{expected_image}">',
            f'<meta name="twitter:image" content="{expected_image}">',
        ]
        missing = [value for value in required if value not in html]
        if missing:
            raise SystemExit("Preview metadata escaped the PR path:\n" + "\n".join(missing))

        unscoped_image = f"{base}{social_image}"
        if unscoped_image in html:
            raise SystemExit(f"Preview metadata still contains unscoped asset URL: {unscoped_image}")

    print("preview social metadata regression test passed")


if __name__ == "__main__":
    main()
