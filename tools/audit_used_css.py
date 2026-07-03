"""Audit CSS selectors against classes/IDs used by built HTML.

This helper is intentionally conservative. It does not try to be a full CSS
parser; it is a practical static-site audit tool for checking which rules from a
large legacy stylesheet still appear relevant to the generated pages.

Typical use after building:

    python tools/audit_used_css.py \
      --html-root ../site-dist \
      --css assets/common/wp-content/themes/Divi/style.css \
      --write-used-css assets/pca-divi-used.generated.css

The generated CSS should still be reviewed visually before replacing the curated
`assets/pca-divi-used.css` file.
"""

from __future__ import annotations

import argparse
import html.parser
import re
from dataclasses import dataclass
from pathlib import Path


CLASS_RE = re.compile(r"\.(-?[_a-zA-Z]+[_a-zA-Z0-9-]*)")
ID_RE = re.compile(r"#(-?[_a-zA-Z]+[_a-zA-Z0-9-]*)")
TAG_RE = re.compile(r"(^|[\s>+~,])([a-zA-Z][a-zA-Z0-9-]*)")
AT_RULE_RE = re.compile(r"@(?:media|supports|document|container|layer)\b")


@dataclass
class UsedMarkup:
    classes: set[str]
    ids: set[str]
    tags: set[str]


class MarkupCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.used = UsedMarkup(classes=set(), ids=set(), tags=set())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.used.tags.add(tag.lower())
        for name, value in attrs:
            if not value:
                continue
            if name == "class":
                self.used.classes.update(part for part in value.split() if part)
            elif name == "id":
                self.used.ids.add(value)


def collect_used_markup(html_root: Path) -> UsedMarkup:
    collector = MarkupCollector()
    for path in sorted(html_root.rglob("*.html")):
        collector.feed(path.read_text(encoding="utf-8", errors="ignore"))
    return collector.used


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def iter_rules(css: str):
    """Yield (selector, body) pairs, keeping nested at-rule contents flattened."""
    css = strip_css_comments(css)
    i = 0
    n = len(css)
    while i < n:
        start = i
        brace = css.find("{", i)
        if brace == -1:
            break
        selector = css[start:brace].strip()
        depth = 1
        j = brace + 1
        while j < n and depth:
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
            j += 1
        body = css[brace + 1:j - 1]
        if selector:
            yield selector, body
        i = j


def selector_matches_used_markup(selector: str, used: UsedMarkup) -> bool:
    selector = selector.strip()
    if not selector:
        return False

    if selector.startswith("@"):
        return bool(AT_RULE_RE.match(selector))

    class_names = set(CLASS_RE.findall(selector))
    id_names = set(ID_RE.findall(selector))
    tag_names = {match.group(2).lower() for match in TAG_RE.finditer(selector)}

    if class_names and class_names.intersection(used.classes):
        return True
    if id_names and id_names.intersection(used.ids):
        return True

    # Keep element-only base rules for tags present in the generated HTML.
    if not class_names and not id_names and tag_names and tag_names.intersection(used.tags):
        return True

    # Keep universal/root/reset selectors conservatively.
    if selector in {"*", "html", "body", "html,body", "html, body"}:
        return True

    return False


def filter_used_css(css: str, used: UsedMarkup) -> tuple[str, int, int]:
    kept: list[str] = []
    kept_count = 0
    total_count = 0

    for selector, body in iter_rules(css):
        total_count += 1
        parts = [part.strip() for part in selector.split(",")]
        matching_parts = [part for part in parts if selector_matches_used_markup(part, used)]
        if not matching_parts:
            continue
        kept_count += 1
        kept.append(",".join(matching_parts) + "{" + body.strip() + "}")

    return "\n".join(kept) + "\n", kept_count, total_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit/filter legacy CSS against generated HTML usage.")
    parser.add_argument("--html-root", required=True, type=Path)
    parser.add_argument("--css", required=True, type=Path, action="append")
    parser.add_argument("--write-used-css", type=Path)
    args = parser.parse_args()

    used = collect_used_markup(args.html_root)
    print(f"HTML root: {args.html_root}")
    print(f"Used classes: {len(used.classes)}")
    print(f"Used IDs:      {len(used.ids)}")
    print(f"Used tags:     {len(used.tags)}")

    combined: list[str] = []
    total_kept = 0
    total_rules = 0

    for css_path in args.css:
        css = css_path.read_text(encoding="utf-8", errors="ignore")
        filtered, kept_count, rule_count = filter_used_css(css, used)
        print(f"{css_path}: kept {kept_count} of {rule_count} top-level rules")
        total_kept += kept_count
        total_rules += rule_count
        combined.append(f"/* Used CSS extracted from {css_path} */\n{filtered}")

    print(f"Total kept: {total_kept} of {total_rules} top-level rules")

    if args.write_used_css:
        args.write_used_css.parent.mkdir(parents=True, exist_ok=True)
        args.write_used_css.write_text("\n".join(combined), encoding="utf-8")
        print(f"Wrote: {args.write_used_css}")


if __name__ == "__main__":
    main()
