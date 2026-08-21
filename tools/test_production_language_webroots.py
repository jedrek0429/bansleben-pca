#!/usr/bin/env python3
"""Regression test for serving each production language from its own webroot."""

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

        destination = root.parent / "public_html"
        run(root, "deploy", "--to", str(destination), "--no-format")

        polish_root = destination / "pl"
        require(polish_root / "index.html", "Polish index")
        require(polish_root / "assets", "Polish assets directory")
        require(polish_root / "contact.php", "Polish contact handler")
        require(polish_root / ".htaccess", "Polish Apache configuration")
        require(polish_root / ".private" / "pca-contact-config.json", "Polish private contact configuration")

        html = (polish_root / "index.html").read_text(encoding="utf-8")
        expected_domain = "https://uprowadzenierodzicielskie.pl"
        if expected_domain not in html:
            raise SystemExit("Polish production HTML does not use the Polish canonical domain")
        if 'href="/assets/' not in html and 'src="/assets/' not in html:
            raise SystemExit("Polish production HTML does not use root-relative assets for a standalone webroot")
        if 'href="/pl/' in html or 'src="/pl/' in html:
            raise SystemExit("Polish production HTML incorrectly requires a /pl URL prefix")

        root_index = (destination / "index.html").read_text(encoding="utf-8")
        if root_index:
            raise SystemExit("Production root index should remain empty; language domains must point at their language directories")

    print("Production language webroot contract passed.")


if __name__ == "__main__":
    main()
