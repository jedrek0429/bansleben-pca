from __future__ import annotations

import argparse
from pathlib import Path

from assets import convert_to_webp
from autofix import autofix_locales
from builder import clean, inspect, site
from hyperlinks import format_content
from workflow import check, deploy, preview

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="build.py")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("site")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--out", default=None)
    c.add_argument("--langs", default=None)
    c.add_argument("--dry", action="store_true")

    c = sub.add_parser("preview")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--prefix", required=True)
    c.add_argument("--to", default=None)
    c.add_argument("--langs", default=None)
    c.add_argument("--no-format", action="store_true")

    c = sub.add_parser("deploy")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--to", default=None)
    c.add_argument("--langs", default=None)
    c.add_argument("--no-format", action="store_true")

    c = sub.add_parser("check")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--strict", action="store_true")
    c.add_argument("--no-autofix-prompt", action="store_true")

    c = sub.add_parser("inspect")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--out", default=None)
    c.add_argument("--prefix", default=None)
    c.add_argument("--preview", action="store_true")
    c.add_argument("--langs", default=None)

    c = sub.add_parser("clean")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--out", default=None)

    c = sub.add_parser("utils")
    u = c.add_subparsers(dest="utility", required=True)
    x = u.add_parser("convert-images")
    x.add_argument("path")
    x = u.add_parser("format-links")
    x.add_argument("--root", default=DEFAULT_ROOT)
    x.add_argument("--check", action="store_true")
    x.add_argument("--self-test", action="store_true")
    x = u.add_parser("autofix-locales")
    x.add_argument("--root", default=DEFAULT_ROOT)

    args = p.parse_args(argv)
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
    elif args.command == "utils" and args.utility == "convert-images":
        convert_to_webp(args.path)
    elif args.command == "utils" and args.utility == "format-links":
        format_content(args.root, check_only=args.check, self_test=args.self_test)
    elif args.command == "utils" and args.utility == "autofix-locales":
        autofix_locales(args.root)
    else:
        raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
