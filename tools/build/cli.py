"""Command-line interface for the PCA builder app."""

from __future__ import annotations

import argparse
from pathlib import Path

from builder import build, clean, inspect
from publisher import publish
from workflow import deploy, format_links, validate

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def add_common_build_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    parser.add_argument("--dest", default=None, help="build output directory; default is root.parent/site-dist")
    parser.add_argument("--url-prefix", default=None, help="optional URL prefix, for example /pr-29")
    parser.add_argument("--lang-in-url", action="store_true", help="enable language roots in generated URLs")
    parser.add_argument("--langs", default=None, help="comma-separated language list, for example en,fr")
    parser.add_argument("--skip-webp", action="store_true", help="skip ImageMagick WebP conversion")
    parser.add_argument("--dry-run", action="store_true", help="load config/templates without writing output")
    parser.add_argument("--strict", action="store_true", help="reserved for warning-as-error validation")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCA builder app.")
    subparsers = parser.add_subparsers(dest="command")

    build_cmd = subparsers.add_parser("build", help="build the static site")
    add_common_build_options(build_cmd)

    validate_cmd = subparsers.add_parser("validate", help="validate locale/config files")
    validate_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    validate_cmd.add_argument("--strict", action="store_true", help="reserved for warning-as-error validation")

    format_cmd = subparsers.add_parser("format-links", help="normalize Markdown hyperlinks")
    format_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    format_cmd.add_argument("--no-save", action="store_true", help="show changes without writing files")
    format_cmd.add_argument("--self-test", action="store_true", help="run hyperlink formatter self-test")

    clean_cmd = subparsers.add_parser("clean", help="remove build output")
    clean_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    clean_cmd.add_argument("--dest", default=None, help="build output directory")

    inspect_cmd = subparsers.add_parser("inspect", help="show resolved build configuration")
    inspect_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    inspect_cmd.add_argument("--dest", default=None, help="build output directory")
    inspect_cmd.add_argument("--url-prefix", default=None, help="optional URL prefix")
    inspect_cmd.add_argument("--lang-in-url", action="store_true", help="enable language roots")
    inspect_cmd.add_argument("--langs", default=None, help="comma-separated language list")

    publish_cmd = subparsers.add_parser("publish", help="publish an existing build output directory")
    publish_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    publish_cmd.add_argument("--dist", default=None, help="build output directory; default is root.parent/site-dist")
    publish_cmd.add_argument("--dest", default=None, help="publish destination; default is root.parent/public_html")
    publish_cmd.add_argument("--langs", default=None, help="comma-separated language list")
    publish_cmd.add_argument("--preserve-root-item", action="append", default=None, help="destination root item to preserve")

    deploy_cmd = subparsers.add_parser("deploy", help="validate, format, build, and publish")
    deploy_cmd.add_argument("--root", default=DEFAULT_ROOT, help="site-src root directory")
    deploy_cmd.add_argument("--dest", default=None, help="publish destination")
    deploy_cmd.add_argument("--url-prefix", default="", help="optional URL prefix")
    deploy_cmd.add_argument("--lang-in-url", action="store_true", help="enable language roots")
    deploy_cmd.add_argument("--write-preview-index", action="store_true", help="write preview redirect index")
    deploy_cmd.add_argument("--preserve-root-item", action="append", default=None, help="destination root item to preserve")
    deploy_cmd.add_argument("--langs", default=None, help="comma-separated language list")
    deploy_cmd.add_argument("--skip-webp", action="store_true", help="skip ImageMagick WebP conversion")
    deploy_cmd.add_argument("--no-format", action="store_true", help="skip hyperlink formatting step")

    # Backward-compatible default build options on the root parser.
    add_common_build_options(parser)
    return parser


def parse_args(argv=None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    command = args.command or "build"

    if command == "build":
        build(
            args.root,
            dest=args.dest,
            url_prefix=args.url_prefix,
            lang_in_url=args.lang_in_url,
            langs=args.langs,
            skip_webp=args.skip_webp,
            dry_run=args.dry_run,
        )
    elif command == "validate":
        validate(args.root, strict=args.strict)
    elif command == "format-links":
        format_links(args.root, no_save=args.no_save, self_test=args.self_test)
    elif command == "clean":
        clean(args.root, dest=args.dest)
    elif command == "inspect":
        inspect(args.root, dest=args.dest, url_prefix=args.url_prefix, lang_in_url=args.lang_in_url, langs=args.langs)
    elif command == "publish":
        root = Path(args.root).expanduser().resolve()
        dist = Path(args.dist).expanduser().resolve() if args.dist else root.parent / "site-dist"
        dest = Path(args.dest).expanduser().resolve() if args.dest else root.parent / "public_html"
        langs = [part.strip() for part in args.langs.split(",")] if args.langs else None
        publish(dist, dest, root=root, langs=langs, preserve_root_item=args.preserve_root_item)
    elif command == "deploy":
        deploy(
            args.root,
            dest=args.dest,
            url_prefix=args.url_prefix,
            lang_in_url=args.lang_in_url,
            write_preview_index_flag=args.write_preview_index,
            preserve_root_item=args.preserve_root_item,
            langs=args.langs,
            skip_webp=args.skip_webp,
            no_format=args.no_format,
        )
    else:
        raise SystemExit(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
