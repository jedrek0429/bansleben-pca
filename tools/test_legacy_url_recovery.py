#!/usr/bin/env python3
"""Regression checks for SEO recovery of legacy WordPress URLs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "build"))

from apache import render_htaccess  # noqa: E402
from context import BuildContext  # noqa: E402


def require(rendered: str, expected: str, message: str) -> None:
    if expected not in rendered:
        raise SystemExit(message)


def main() -> None:
    ctx = BuildContext.from_root(ROOT)
    ctx.load_configs()
    locales = ctx.load_locales()
    legacy = json.loads((ROOT / "config" / "legacy_urls.json").read_text(encoding="utf-8"))

    rendered_by_lang = {}
    for lang in ctx.langs:
        rendered = render_htaccess(ctx, lang, ctx.seo_config, locales)
        rendered_by_lang[lang] = rendered
        require(rendered, "RewriteRule ^wp-login\\.php$ - [G,L,NC]", f"{lang}: WordPress login URL is not explicitly retired")
        require(rendered, "RewriteRule ^wp-content(?:/|$) - [G,L,NC]", f"{lang}: WordPress content tree is not explicitly retired")
        require(rendered, "RewriteCond %{QUERY_STRING} ^p=\\d+(?:&.*)?$ [NC]", f"{lang}: WordPress ?p= post URLs are not explicitly retired")
        require(rendered, "RewriteCond %{QUERY_STRING} (?:^|&)inventoryId=[^&]* [NC]", f"{lang}: compromised inventoryId variants are not canonicalised")

        for source, target in (legacy.get("redirects", {}).get(lang, {}) or {}).items():
            escaped = source.strip("/").replace(".", "\\.")
            expected = f"RedirectMatch 301 ^/{escaped}/?$ {target}"
            require(rendered, expected, f"{lang}: missing exact configured legacy redirect {source!r}")

    en = rendered_by_lang["en"]
    require(en, "RewriteRule ^(?:2023|2026)(?:/|$) - [G,L,NC]", "en: obsolete dated URL trees are not retired")
    require(en, "RedirectMatch 301 ^/qui-sommes-nous/?$ https://enlevementparentalpologne.pl/qui-sommes-nous/", "en: old French about page is not redirected to the French domain")
    require(en, "RedirectMatch 301 ^/polityka-prywatnosci/?$ https://uprowadzenierodzicielskie.pl/polityka-prywatnosci/", "en: old Polish privacy page is not redirected to the Polish domain")

    fr = rendered_by_lang["fr"]
    require(fr, "RewriteRule ^(?:film|giochi-giocattoli|libri)(?:/|$) - [G,L,NC]", "fr: compromised Italian catalogue trees are not retired")
    require(fr, "RewriteRule ^(?:offerte-libri-inglese|shop|assistenza|audiolibri-inglese|contattaci|convenzioni|ebook-inglese|eventi|franchising-feltrinelli|registrati|search-advanced|vinili)(?:/|$) - [G,L,NC]", "fr: compromised Italian spam routes are not retired")
    require(fr, "RewriteRule ^.+-[0-9]{5,}(?:/|$) - [G,L,NC]", "fr: compromised product-ID slug family is not retired")

    print("Legacy URL recovery rules passed for: " + ", ".join(ctx.langs))


if __name__ == "__main__":
    main()
