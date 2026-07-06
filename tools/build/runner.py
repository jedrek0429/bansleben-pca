from __future__ import annotations

import argparse
from pathlib import Path

from assets import convert_to_webp
from autofix import autofix_locales
from builder import clean, inspect, site
from hyperlinks import format_content
from workflow import check, deploy, preview

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
EPILOG = """
Examples:
  build.py check --root .
  build.py site --root . --dry
  build.py site --root .
  build.py preview --root . --to ../public_html/preview/pr-29 --prefix pr-29
  build.py deploy --root . --to ../public_html
  build.py utils autofix-locales --root .
  build.py utils format-links --root . --check
  build.py utils convert-images assets
"""


def add_root_arg(command: argparse.ArgumentParser) -> None:
    command.add_argument("--root", default=DEFAULT_ROOT, help="site source root; default: repository root")


def add_langs_arg(command: argparse.ArgumentParser) -> None:
    command.add_argument("--langs", default=None, help="comma-separated languages, e.g. en,fr,hr")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="PCA builder app for local builds, PR previews, production deploys, checks, and utilities.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(title="commands", dest="command", required=True)

    cmd = sub.add_parser("site", help="build local static site output", description="Build the site into ../site-dist or a custom output directory.")
    add_root_arg(cmd)
    cmd.add_argument("--out", default=None, help="output directory; default: root.parent/site-dist")
    add_langs_arg(cmd)
    cmd.add_argument("--dry", action="store_true", help="load config, locales, and templates without writing output")

    cmd = sub.add_parser("preview", help="build and publish a PR preview", description="Build preview output with a URL prefix and publish it to a preview directory.")
    add_root_arg(cmd)
    cmd.add_argument("--prefix", required=True, help="preview URL prefix, e.g. pr-29")
    cmd.add_argument("--to", default=None, help="preview destination; default: root.parent/public_html/preview/<prefix>")
    add_langs_arg(cmd)
    cmd.add_argument("--no-format", action="store_true", help="skip Markdown hyperlink normalization before building")

    cmd = sub.add_parser("deploy", help="build and publish production", description="Run checks, build production output, and publish to public_html.")
    add_root_arg(cmd)
    cmd.add_argument("--to", default=None, help="production destination; default: root.parent/public_html")
    add_langs_arg(cmd)
    cmd.add_argument("--no-format", action="store_true", help="skip Markdown hyperlink normalization before building")

    cmd = sub.add_parser("check", help="validate config and locales", description="Validate site configuration and locale JSON files.")
    add_root_arg(cmd)
    cmd.add_argument("--strict", action="store_true", help="treat warnings as failures")
    cmd.add_argument("--no-autofix-prompt", action="store_true", help="do not offer to run utils autofix-locales on failure")

    cmd = sub.add_parser("inspect", help="show resolved builder configuration", description="Print resolved root, output, mode, prefix, languages, and page count.")
    add_root_arg(cmd)
    cmd.add_argument("--out", default=None, help="output directory to inspect")
    cmd.add_argument("--prefix", default=None, help="preview prefix to inspect")
    cmd.add_argument("--preview", action="store_true", help="inspect preview URL mode")
    add_langs_arg(cmd)

    cmd = sub.add_parser("clean", help="remove generated output", description="Delete the generated output directory.")
    add_root_arg(cmd)
    cmd.add_argument("--out", default=None, help="output directory; default: root.parent/site-dist")

    cmd = sub.add_parser("utils", help="maintenance utilities", description="Run focused maintenance tasks for content, locales, and assets.")
    utilities = cmd.add_subparsers(title="utilities", dest="utility", required=True)

    util = utilities.add_parser("autofix-locales", help="repair locale drift", description="Repair fixable locale JSON drift from config/pages.json and locales/en.json.")
    add_root_arg(util)

    util = utilities.add_parser("format-links", help="normalize Markdown links", description="Normalize bare URLs and emails in Markdown content files.")
    add_root_arg(util)
    util.add_argument("--check", action="store_true", help="report changes without writing files")
    util.add_argument("--self-test", action="store_true", help="run formatter self-test")

    util = utilities.add_parser("convert-images", help="convert images to WebP", description="Convert PNG/JPEG files below a directory to WebP when ImageMagick is available.")
    util.add_argument("path", help="directory containing images")

    return parser


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "site":
        site(args.root, out=args.out, langs=args.langs, dry=args.dry)
    elif args.command == "preview":
        preview(args.root, prefix=args.prefix, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "deploy":
        deploy(args.root, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "check":
        check(args.root, strict=args.strict, autofix_prompt=not args.no_autofix_prompt)
    elif args.command == "inspect":
        inspect(args.root, out=args.out, prefix=args.prefix, preview=args.preview, langs=args.langs)
    elif args.command == "clean":
        clean(args.root, out=args.out)
    elif args.command == "utils" and args.utility == "autofix-locales":
        autofix_locales(args.root)
    elif args.command == "utils" and args.utility == "format-links":
        format_content(args.root, check_only=args.check, self_test=args.self_test)
    elif args.command == "utils" and args.utility == "convert-images":
        convert_to_webp(args.path)
    else:
        raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
