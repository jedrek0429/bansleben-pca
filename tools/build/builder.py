"""Top-level site build orchestration."""

from __future__ import annotations

import shutil

from common import CLR_GREEN, CLR_WHITE, color, display_path, print_labeled, print_section

from apache import write_htaccess_files
from assets import convert_to_webp, copy_static
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


def make_context(root, *, out=None, prefix=None, preview: bool = False, langs=None) -> BuildContext:
    return BuildContext.from_root(
        root,
        dist=out,
        url_prefix=prefix,
        lang_in_url=preview,
        langs=langs,
    )


def inspect(root, *, out=None, prefix=None, preview: bool = False, langs=None) -> BuildContext:
    ctx = make_context(root, out=out, prefix=prefix, preview=preview, langs=langs)
    ctx.load_configs()
    print_section("Builder configuration")
    print(color(f"Root:      {display_path(ctx.root, ctx.root.parent)}", CLR_WHITE))
    print(color(f"Output:    {display_path(ctx.dist, ctx.root.parent)}", CLR_WHITE))
    print(color(f"Mode:      {'preview' if ctx.lang_in_url else 'site'}", CLR_WHITE))
    print(color(f"Prefix:    {ctx.url_prefix or '/'}", CLR_WHITE))
    print(color(f"Languages: {', '.join(ctx.langs)}", CLR_WHITE))
    print(color(f"Pages:     {len(ctx.pages_config.get('pages', []))}", CLR_WHITE))
    return ctx


def clean(root, *, out=None) -> None:
    ctx = make_context(root, out=out)
    print_section("Clean output")
    print(color(f"Output: {display_path(ctx.dist, ctx.root.parent)}", CLR_WHITE))
    if ctx.dist.exists():
        shutil.rmtree(ctx.dist)
        print_labeled("OK", CLR_GREEN, "removed output.")
    else:
        print_labeled("OK", CLR_GREEN, "nothing to clean.")


def site(root, *, out=None, langs=None, dry: bool = False, prefix: str | None = None, preview: bool = False) -> BuildContext:
    """Build the site into the selected output directory."""
    ctx = make_context(root, out=out, prefix=prefix, preview=preview, langs=langs)

    print_section("Build site")
    print(color(f"Root:   {display_path(ctx.root, ctx.root.parent)}", CLR_WHITE))
    print(color(f"Output: {display_path(ctx.dist, ctx.root.parent)}", CLR_WHITE))
    print(color(f"Mode:   {'preview' if preview else 'site'}", CLR_WHITE))

    ctx.load_configs()
    locales = ctx.load_locales()
    load_templates(ctx)

    if dry:
        print_labeled("OK", CLR_GREEN, "dry check completed; config, locales, and templates are loadable.")
        return ctx

    if ctx.dist.exists():
        shutil.rmtree(ctx.dist)
    ctx.dist.mkdir(parents=True, exist_ok=True)

    render_templates(ctx, locales)

    redirect_lang = ctx.langs[0] if ctx.langs else "en"
    redirect_target = f"{ctx.url_prefix}/{redirect_lang}/" if ctx.url_prefix else f"/{redirect_lang}/"
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
    return ctx


# Programmatic alias kept inside the app; CLI no longer exposes a vague `build` command.
build = site
