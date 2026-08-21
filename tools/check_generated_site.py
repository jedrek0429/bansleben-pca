from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


IGNORED_SCHEMES = {"mailto", "tel", "javascript", "data"}


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.canonicals: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        data = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag in {"a", "link"} and data.get("href"):
            self.references.append(data["href"])
        if tag in {"img", "script", "iframe", "source"} and data.get("src"):
            self.references.append(data["src"])
        if tag == "form" and data.get("action"):
            self.references.append(data["action"])
        if tag in {"button", "input"} and data.get("formaction"):
            self.references.append(data["formaction"])
        if tag in {"img", "source"} and data.get("srcset"):
            for candidate in data["srcset"].split(","):
                candidate = candidate.strip()
                if candidate:
                    self.references.append(candidate.split(None, 1)[0])
        if tag == "link" and data.get("rel", "").lower() == "canonical" and data.get("href"):
            self.canonicals.append(data["href"])


def local_target(root: Path, page: Path, reference: str, prefix: str) -> Path | None:
    value = str(reference or "").strip()
    if not value or value.startswith("#") or value.startswith("//"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme:
        if parsed.scheme.lower() in IGNORED_SCHEMES or parsed.netloc:
            return None
    path = unquote(parsed.path)
    if not path:
        return None
    normalized_prefix = "/" + prefix.strip("/") if prefix.strip("/") else ""
    if path.startswith("/"):
        if normalized_prefix:
            if path == normalized_prefix:
                path = "/"
            elif path.startswith(normalized_prefix + "/"):
                path = path[len(normalized_prefix):]
        target = root / path.lstrip("/")
    else:
        target = page.parent / path
    target = target.resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return target
    return target


def existing_target(path: Path) -> bool:
    if path.is_file():
        return True
    if path.is_dir() and (path / "index.html").is_file():
        return True
    if path.suffix == "" and (path / "index.html").is_file():
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate internal references in generated PCA output.")
    parser.add_argument("--root", required=True, help="Generated site root for one URL prefix")
    parser.add_argument("--prefix", default="", help="URL prefix used for the build, e.g. pr-44")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    html_files = sorted(root.rglob("*.html"))
    if not html_files:
        raise SystemExit(f"No generated HTML found under {root}")

    missing: dict[str, set[str]] = {}
    canonical_pages: dict[str, list[str]] = {}

    for page in html_files:
        document = ReferenceParser()
        document.feed(page.read_text(encoding="utf-8"))
        rel_page = page.relative_to(root).as_posix()
        for canonical in document.canonicals:
            canonical_pages.setdefault(canonical, []).append(rel_page)
        for reference in document.references:
            target = local_target(root, page, reference, args.prefix)
            if target is None or existing_target(target):
                continue
            missing.setdefault(reference, set()).add(rel_page)

    duplicate_canonicals = {
        canonical: pages
        for canonical, pages in canonical_pages.items()
        if canonical and len(pages) > 1
    }

    errors = 0
    if missing:
        errors += len(missing)
        print("Broken generated-site references:")
        for reference, pages in sorted(missing.items()):
            print(f"  {reference} <- {', '.join(sorted(pages)[:5])}")
    if duplicate_canonicals:
        errors += len(duplicate_canonicals)
        print("Duplicate canonical URLs:")
        for canonical, pages in sorted(duplicate_canonicals.items()):
            print(f"  {canonical} <- {', '.join(pages)}")

    if errors:
        raise SystemExit(1)
    print(f"Generated-site integrity OK: {len(html_files)} HTML files checked.")


if __name__ == "__main__":
    main()
