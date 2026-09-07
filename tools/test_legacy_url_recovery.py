#!/usr/bin/env python3
"""Regression tests for SEO recovery of legacy WordPress URLs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "build"))

from apache import render_htaccess  # noqa: E402
from context import BuildContext  # noqa: E402


def main() -> None:
    ctx = BuildContext.from_root(ROOT)
    ctx.load_configs()
    locales = ctx.load_locales()
    legacy = json.loads((ROOT / "config" / "legacy_urls.json").read_text(encoding="utf-8"))

    for lang in ctx.langs:
        rendered = render_htaccess(ctx, lang, ctx.seo_config, locales)
        if "Redirect gone /wp-login.php" not in rendered:
            raise SystemExit(f"{lang}: WordPress login URL is not explicitly retired")
        if "RewriteRule ^wp-content(?:/|$) - [G,L,NC]" not in rendered:
            raise SystemExit(f"{lang}: WordPress content tree is not explicitly retired")

        for source, target in (legacy.get("redirects", {}).get(lang, {}) or {}).items():
            expected = f"Redirect 301 /{source.strip('/')} {target}"
            if expected not in rendered:
                raise SystemExit(f"{lang}: missing configured legacy redirect {source!r}")

    print("Legacy URL recovery rules passed for: " + ", ".join(ctx.langs))


if __name__ == "__main__":
    main()
