"""Command-line interface for the PCA builder app."""

from __future__ import annotations

import argparse
from pathlib import Path

from assets import convert_to_webp
from builder import clean, inspect, site
from workflow import check, deploy, format_content, preview

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description="PCA site builder: build, preview, deploy, check content, and run maintenance utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    site_cmd = subparsers.add_parser("site", help="build the site into a local output directory")
    site_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    site_cmd.add_argument("--out", default=None, help="output directory; default: root.parent/site-dist")
    site_cmd.add_argument("--langs", default=None, help="comma-separated languages, e.g. en,fr,hr")
    site_cmd.add_argument("--dry", action="store_true", help="load config/templates without writing output")

    preview_cmd = subparsers.add_parser("preview", help="build and publish a pull-request preview")
    preview_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    preview_cmd.add_argument("--prefix", required=True, help="preview URL prefix, e.g. pr-29")
    preview_cmd.add_argument("--to", default=None, help="preview destination directory")
    preview_cmd.add_argument("--langs", default=None, help="comma-separated languages")
    preview_cmd.add_argument("--no-format", action="store_true", help="skip Markdown hyperlink normalization")

    deploy_cmd = subparsers.add_parser("deploy", help="check, build, and publish production")
    deploy_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    deploy_cmd.add_argument("--to", default=None, help="production destination directory; default: root.parent/public_html")
    deploy_cmd.add_argument("--langs", default=None, help="comma-separated languages")
    deploy_cmd.add_argument("--no-format", action="store_true", help="skip Markdown hyperlink normalization")

    check_cmd = subparsers.add_parser("check", help="validate site configuration and locale files")
    check_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    check_cmd.add_argument("--strict", action="store_true", help="treat warnings as errors when supported")

    format_cmd = subparsers.add_parser("format", help="normalize Markdown hyperlinks in content")
    format_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    format_cmd.add_argument("--check", action="store_true", help="show changes without writing files")
    format_cmd.add_argument("--self-test", action="store_true", help="run formatter self-test")

    inspect_cmd = subparsers.add_parser("inspect", help="show resolved builder configuration")
    inspect_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    inspect_cmd.add_argument("--out", default=None, help="output directory")
    inspect_cmd.add_argument("--prefix", default=None, help="preview prefix to inspect")
    inspect_cmd.add_argument("--preview", action="store_true", help="inspect preview URL mode")
    inspect_cmd.add_argument("--langs", default=None, help="comma-separated languages")

    clean_cmd = subparsers.add_parser("clean", help="remove generated output")
    clean_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site source root")
    clean_cmd.add_argument("--out", default=None, help="output directory")

    utils_cmd = subparsers.add_parser("utils", help="maintenance utilities")
    utils_sub = utils_cmd.add_subparsers(dest="utility", required=True)
    convert_cmd = utils_sub.add_parser("convert-images", help="convert PNG/JPEG files below a directory to WebP")
    convert_cmd.add_argument("path", help="directory containing images")

    return parser


def parse_args(argv=None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    if args.command == "site":
        site(args.root, out=args.out, langs=args.langs, dry=args.dry)
    elif args.command == "preview":
        preview(args.root, prefix=args.prefix, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "deploy":
        deploy(args.root, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "check":
        check(args.root, strict=args.strict)
    elif args.command == "format":
        format_content(args.root, check_only=args.check, self_test=args.self_test)
    elif args.command == "inspect":
        inspect(args.root, out=args.out, prefix=args.prefix, preview=args.preview, langs=args.langs)
    elif args.command == "clean":
        clean(args.root, out=args.out)
    elif args.command == "utils" and args.utility == "convert-images":
        convert_to_webp(args.path)
    else:
        raise SystemExit("Unknown command.")


if __name__ == "__main__":
    main()
