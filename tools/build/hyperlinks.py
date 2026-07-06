"""Markdown hyperlink normalization."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, CLR_WHITE, CLR_YELLOW, color, display_path, print_group, print_labeled, print_section

CONTENT_DIR = "content"
URL_PREFIX_PATTERN = r"(?:https?://|www\.)"
EMAIL_ADDRESS_PATTERN_TEXT = r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"

BARE_URL_PATTERN = re.compile(rf"\b{URL_PREFIX_PATTERN}[^\s<>\[\]\"'`]+", re.IGNORECASE)
BARE_MAILTO_PATTERN = re.compile(rf"(?<![\w.+\-])(mailto:{EMAIL_ADDRESS_PATTERN_TEXT}(?:\?[^\s<>\[\]\"'`]*)?)", re.IGNORECASE)
BARE_EMAIL_PATTERN = re.compile(rf"(?<![\w.+\-])({EMAIL_ADDRESS_PATTERN_TEXT})(?![\w.\-])", re.IGNORECASE)
AUTOLINK_PATTERN = re.compile(rf"<({URL_PREFIX_PATTERN}[^>\s]+|mailto:[^>\s]+|{EMAIL_ADDRESS_PATTERN_TEXT})>", re.IGNORECASE)
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[([^\]\n]+)\]\(\s*([^\s)]+)([ \t]+(?:\"[^\"]*\"|'[^']*'))?\s*\)", re.IGNORECASE)
ALL_MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]\n]+\]\([^\n)]*\)", re.IGNORECASE)
PROTECTED_PATTERNS = [
    re.compile(r"(?ms)^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[ \t]*$"),
    re.compile(r"`[^`\n]+`"),
    re.compile(rf"!\[[^\]\n]*\]\(\s*[^\)\n]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^\)\n]*\)", re.IGNORECASE),
    re.compile(rf"(?m)^[ \t]{{0,3}}\[[^\]\n]+\]:[ \t]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^\s]*.*$", re.IGNORECASE),
    re.compile(r"<img\b[\s\S]*?>", re.IGNORECASE),
    re.compile(rf"<(?!https?://|www\.|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT}>)[A-Za-z][^>\n]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^>\n]*>", re.IGNORECASE),
]


def protect_regions(content: str, patterns: list[re.Pattern], marker_name: str) -> tuple[str, list[str]]:
    protected = []
    def protect_match(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"@@URL_FORMATTER_{marker_name}_{len(protected) - 1}@@"
    for pattern in patterns:
        content = pattern.sub(protect_match, content)
    return content, protected


def restore_regions(content: str, protected: list[str], marker_name: str) -> str:
    for index, original in enumerate(protected):
        content = content.replace(f"@@URL_FORMATTER_{marker_name}_{index}@@", original)
    return content


def split_trailing_punctuation(value: str) -> tuple[str, str]:
    trailing = ""
    while value and value[-1] in ".,;:!?":
        trailing = value[-1] + trailing
        value = value[:-1]
    while value.endswith(")") and value.count(")") > value.count("("):
        trailing = ")" + trailing
        value = value[:-1]
    return value, trailing


def is_web_url_like(text: str) -> bool:
    return re.match(rf"^{URL_PREFIX_PATTERN}", text.strip(), re.IGNORECASE) is not None


def is_mailto_like(text: str) -> bool:
    return re.match(r"^mailto:", text.strip(), re.IGNORECASE) is not None


def is_email_like(text: str) -> bool:
    return re.match(rf"^{EMAIL_ADDRESS_PATTERN_TEXT}$", text.strip(), re.IGNORECASE) is not None


def make_web_href(url: str) -> str:
    return f"https://{url}" if url.lower().startswith("www.") else url


def make_web_display_text(url: str) -> str:
    display_text = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    return re.sub(r"^www\.", "", display_text, flags=re.IGNORECASE)


def make_web_markdown_link(url: str, title: str = "") -> str:
    return f"[{make_web_display_text(url)}]({make_web_href(url)}{title})"


def make_mail_href(value: str) -> str:
    return value if value.lower().startswith("mailto:") else f"mailto:{value}"


def make_mail_display_text(value: str) -> str:
    return re.sub(r"^mailto:", "", value, flags=re.IGNORECASE).split("?", 1)[0]


def make_mail_markdown_link(value: str, title: str = "") -> str:
    return f"[{make_mail_display_text(value)}]({make_mail_href(value)}{title})"


def log_change(changes: list[str], original: str, formatted: str) -> None:
    if original != formatted:
        changes.append(f"{original} -> {formatted}")


def normalize_existing_markdown_links(content: str, changes: list[str]) -> str:
    def replace_link(match: re.Match) -> str:
        label, destination, title = match.group(1), match.group(2), match.group(3) or ""
        if is_web_url_like(destination) and is_web_url_like(label):
            formatted = make_web_markdown_link(destination, title)
            log_change(changes, match.group(0), formatted)
            return formatted
        if is_mailto_like(destination) and (is_mailto_like(label) or is_email_like(label)):
            formatted = make_mail_markdown_link(destination, title)
            log_change(changes, match.group(0), formatted)
            return formatted
        return match.group(0)
    return MARKDOWN_LINK_PATTERN.sub(replace_link, content)


def normalize_autolinks(content: str, changes: list[str]) -> str:
    def replace_autolink(match: re.Match) -> str:
        value = match.group(1)
        if is_web_url_like(value):
            formatted = make_web_markdown_link(value)
        elif is_mailto_like(value) or is_email_like(value):
            formatted = make_mail_markdown_link(value)
        else:
            return match.group(0)
        log_change(changes, match.group(0), formatted)
        return formatted
    return AUTOLINK_PATTERN.sub(replace_autolink, content)


def normalize_bare_urls(content: str, changes: list[str]) -> str:
    def replace_url(match: re.Match) -> str:
        raw_url = match.group(0)
        url, trailing = split_trailing_punctuation(raw_url)
        if not url:
            return raw_url
        formatted = make_web_markdown_link(url)
        log_change(changes, url, formatted)
        return f"{formatted}{trailing}"
    return BARE_URL_PATTERN.sub(replace_url, content)


def normalize_bare_mailto_links(content: str, changes: list[str]) -> str:
    def replace_mailto(match: re.Match) -> str:
        raw_mailto = match.group(1)
        mailto_value, trailing = split_trailing_punctuation(raw_mailto)
        if not mailto_value:
            return raw_mailto
        formatted = make_mail_markdown_link(mailto_value)
        log_change(changes, mailto_value, formatted)
        return f"{formatted}{trailing}"
    return BARE_MAILTO_PATTERN.sub(replace_mailto, content)


def normalize_bare_emails(content: str, changes: list[str]) -> str:
    def replace_email(match: re.Match) -> str:
        email = match.group(1)
        formatted = make_mail_markdown_link(email)
        log_change(changes, email, formatted)
        return formatted
    return BARE_EMAIL_PATTERN.sub(replace_email, content)


def normalize_content(content: str) -> tuple[str, list[str]]:
    protected_content, protected = protect_regions(content, PROTECTED_PATTERNS, "PROTECTED")
    changes = []
    protected_content = normalize_existing_markdown_links(protected_content, changes)
    protected_content = normalize_autolinks(protected_content, changes)
    protected_content, markdown_links_before_bare_urls = protect_regions(protected_content, [ALL_MARKDOWN_LINK_PATTERN], "MARKDOWN_BEFORE_BARE_URLS")
    protected_content = normalize_bare_urls(protected_content, changes)
    protected_content = normalize_bare_mailto_links(protected_content, changes)
    protected_content, markdown_links_before_bare_emails = protect_regions(protected_content, [ALL_MARKDOWN_LINK_PATTERN], "MARKDOWN_BEFORE_BARE_EMAILS")
    protected_content = normalize_bare_emails(protected_content, changes)
    protected_content = restore_regions(protected_content, markdown_links_before_bare_emails, "MARKDOWN_BEFORE_BARE_EMAILS")
    protected_content = restore_regions(protected_content, markdown_links_before_bare_urls, "MARKDOWN_BEFORE_BARE_URLS")
    return restore_regions(protected_content, protected, "PROTECTED"), changes


def format_hyperlinks(file: str | Path, check_only: bool = False) -> list[str]:
    path = Path(file)
    content = path.read_text(encoding="utf-8")
    updated_content, changes = normalize_content(content)
    if changes and not check_only:
        path.write_text(updated_content, encoding="utf-8")
    return changes


def markdown_files(root: Path) -> list[Path]:
    return sorted((root / CONTENT_DIR).rglob("*.md"))


def run_self_test() -> None:
    cases = {
        "Web: https://www.example.com/a/b?x=1#section.": "Web: [example.com/a/b?x=1#section](https://www.example.com/a/b?x=1#section).",
        "Email: user@example.com": "Email: [user@example.com](mailto:user@example.com)",
        "HTML: <img src=\"https://www.example.com/image.png\">": "HTML: <img src=\"https://www.example.com/image.png\">",
    }
    failed = False
    for source, expected in cases.items():
        actual, _changes = normalize_content(source)
        if actual != expected:
            failed = True
            print("FAILED")
            print(f"Source:   {source}")
            print(f"Expected: {expected}")
            print(f"Actual:   {actual}")
    if failed:
        raise SystemExit(1)
    print("Self-test passed.")


def format_content(root, *, check_only: bool = False, self_test: bool = False) -> None:
    if self_test:
        run_self_test()
        return
    root = Path(root).expanduser().resolve()
    content_dir = root / CONTENT_DIR
    term_width = min(shutil.get_terminal_size((120, 20)).columns, 140)
    if not content_dir.is_dir():
        print_labeled("ERROR", CLR_RED, f"Content directory not found: {display_path(content_dir, root.parent)}")
        raise SystemExit(2)
    files = markdown_files(root)
    files_changed = 0
    print_section("Hyperlink Format Report", term_width)
    print(color(f"Source:        {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Files found:   {len(files)}", CLR_WHITE))
    for file in files:
        changes = format_hyperlinks(file, check_only=check_only)
        if changes:
            files_changed += 1
            print_group(f"Formatted hyperlinks in {display_path(file, root.parent)}", changes, "OK", CLR_GREEN)
    if check_only:
        print_labeled("INFO", CLR_YELLOW, "No changes were saved to files.")
    elif files_changed:
        print_labeled("OK", CLR_GREEN, f"{files_changed} files changed.")
    else:
        print_labeled("OK", CLR_GREEN, "no changes needed.")
