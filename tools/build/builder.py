"""Top-level build orchestration."""

from __future__ import annotations

import shutil

from common import CLR_GREEN, CLR_WHITE, color, display_path, print_labeled, print_section

from apache import write_htaccess_files
from assets import convert_to_webp, copy_assets_to, copy_static
from context import BuildContext
from pages import render_404, render_localized_page
from sitemap import lang_output_dir, write_extra_seo_files
from template_engine import load_templates


def render_templates(ctx: BuildContext, locales) -> None:
    """Load templates and render every enabled page for every language."""
    templates = load_templates(ctx)

    for lang in ctx.langs:
        for page in ctx.pages_config.get("pages", []):
            render_localized_page(ctx, locales, lang, page, templates)
        render_404(ctx, lang, locales, templates)
        copy_static(ctx, lang)

        lang_root = lang_output_dir(ctx, lang)
        write_extra_seo_files(ctx, ctx.seo_config, locales, lang, lang_root)
        write_htaccess_files(ctx, ctx.seo_config, locales, lang, lang_root)

    if ctx.lang_in_url:
        copy_assets_to(ctx, ctx.dist)


def build(root) -> None:
    """Build the static site into the sibling site-dist directory."""
    ctx = BuildContext.from_root(root)

    print_section("Build static site")
    print(color(f"Root: {display_path(ctx.root, ctx.root.parent)}", CLR_WHITE))
    print(color(f"Dist: {display_path(ctx.dist, ctx.root.parent)}", CLR_WHITE))

    if ctx.dist.exists():
        shutil.rmtree(ctx.dist)
    ctx.dist.mkdir(parents=True, exist_ok=True)

    ctx.load_configs()
    locales = ctx.load_locales()
    render_templates(ctx, locales)

    for lang in ctx.langs:
        (ctx.dist / lang).mkdir(parents=True, exist_ok=True)

    redirect_target = f"/{ctx.langs[0]}/" if ctx.langs else "/en/"
    (ctx.dist / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url='
        + redirect_target
        + '"><link rel="canonical" href="'
        + redirect_target
        + '"><title>Redirecting…</title>',
        encoding="utf-8",
    )

    convert_to_webp(str(ctx.dist))
    print_labeled("OK", CLR_GREEN, f"built {display_path(ctx.dist, ctx.root.parent)}")
