from __future__ import annotations

import argparse
from pathlib import Path

from assets import convert_to_webp
from builder import clean, inspect, site
from hyperlinks import format_content
from workflow import check, deploy, preview

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="build.py", description="PCA site builder.")
    commands = root.add_subparsers(dest="command", required=True)

    site_cmd = commands.add_parser("site", help="build local site output")
    site_cmd.add_argument("--root", default=DEFAULT_ROOT)
    site_cmd.add_argument("--out", default=None)
    site_cmd.add_argument("--langs", default=None)
    site_cmd.add_argument("--dry", action="store_true")

    preview_cmd = commands.add_parser("preview", help="build and publish PR preview")
    preview_cmd.add_argument("--root", default=DEFAULT_ROOT)
    preview_cmd.add_argument("--prefix", required=True)
    preview_cmd.add_argument("--to", default=None)
    preview_cmd.add_argument("--langs", default=None)
    preview_cmd.add_argument("--no-format", action="store_true")

    deploy_cmd = commands.add_parser("deploy", help="build and publish production")
    deploy_cmd.add_argument("--root", default=DEFAULT_ROOT)
    deploy_cmd.add_argument("--to", default=None)
    deploy_cmd.add_argument("--langs", default=None)
    deploy_cmd.add_argument("--no-format", action="store_true")

    check_cmd = commands.add_parser("check", help="validate site config and locales")
    check_cmd.add_argument("--root", default=DEFAULT_ROOT)
    check_cmd.add_argument("--strict", action="store_true")

    inspect_cmd = commands.add_parser("inspect", help="show resolved builder config")
    inspect_cmd.add_argument("--root", default=DEFAULT_ROOT)
    inspect_cmd.add_argument("--out", default=None)
    inspect_cmd.add_argument("--prefix", default=None)
    inspect_cmd.add_argument("--preview", action="store_true")
    inspect_cmd.add_argument("--langs", default=None)

    clean_cmd = commands.add_parser("clean", help="remove generated output")
    clean_cmd.add_argument("--root", default=DEFAULT_ROOT)
    clean_cmd.add_argument("--out", default=None)

    utils_cmd = commands.add_parser("utils", help="maintenance utilities")
    utilities = utils_cmd.add_subparsers(dest="utility", required=True)
    images_cmd = utilities.add_parser("convert-images", help="convert images to WebP")
    images_cmd.add_argument("path")
    links_cmd = utilities.add_parser("format-links", help="normalize Markdown links")
    links_cmd.add_argument("--root", default=DEFAULT_ROOT)
    links_cmd.add_argument("--check", action="store_true")
    links_cmd.add_argument("--self-test", action="store_true")

    return root


def main(argv=None) -> None:
    args = parser().parse_args(argv)
    if args.command == "site":
        site(args.root, out=args.out, langs=args.langs, dry=args.dry)
    elif args.command == "preview":
        preview(args.root, prefix=args.prefix, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "deploy":
        deploy(args.root, to=args.to, langs=args.langs, clean_content=not args.no_format)
    elif args.command == "check":
        check(args.root, strict=args.strict)
    elif args.command == "inspect":
        inspect(args.root, out=args.out, prefix=args.prefix, preview=args.preview, langs=args.langs)
    elif args.command == "clean":
        clean(args.root, out=args.out)
    elif args.command == "utils" and args.utility == "convert-images":
        convert_to_webp(args.path)
    elif args.command == "utils" and args.utility == "format-links":
        format_content(args.root, check_only=args.check, self_test=args.self_test)
    else:
        raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
