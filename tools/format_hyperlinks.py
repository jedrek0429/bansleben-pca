"""
Goes through the .md files in site-src/content/ and normalizes links.

Examples:
    https://www.example.com/path -> [example.com/path](https://www.example.com/path)
    http://www.example.com/path  -> [example.com/path](http://www.example.com/path)
    www.example.com/path         -> [example.com/path](https://www.example.com/path)

    name@example.com             -> [name@example.com](mailto:name@example.com)
    mailto:name@example.com      -> [name@example.com](mailto:name@example.com)
    <mailto:name@example.com>    -> [name@example.com](mailto:name@example.com)
    <name@example.com>           -> [name@example.com](mailto:name@example.com)

Preserves:
    - URL paths, query strings, and fragments
    - Markdown images
    - custom Markdown link labels
    - code blocks
    - inline code
    - HTML tags/images

Usage:
    python format_hyperlinks.py --root path/to/site-src --no-save
    python format_hyperlinks.py --self-test
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

from common import (
    CLR_GREEN,
    CLR_RED,
    CLR_YELLOW,
    CLR_WHITE,
    color,
    display_path,
    print_group,
    print_labeled,
    print_section,
)


CONTENT_DIR = "content"

URL_PREFIX_PATTERN = r"(?:https?://|www\.)"
EMAIL_ADDRESS_PATTERN_TEXT = r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}"

BARE_URL_PATTERN = re.compile(
    rf"\b{URL_PREFIX_PATTERN}[^\s<>\[\]\"'`]+",
    re.IGNORECASE,
)

BARE_MAILTO_PATTERN = re.compile(
    rf"(?<![\w.+\-])(mailto:{EMAIL_ADDRESS_PATTERN_TEXT}(?:\?[^\s<>\[\]\"'`]*)?)",
    re.IGNORECASE,
)

BARE_EMAIL_PATTERN = re.compile(
    rf"(?<![\w.+\-])({EMAIL_ADDRESS_PATTERN_TEXT})(?![\w.\-])",
    re.IGNORECASE,
)

AUTOLINK_PATTERN = re.compile(
    rf"<({URL_PREFIX_PATTERN}[^>\s]+|mailto:[^>\s]+|{EMAIL_ADDRESS_PATTERN_TEXT})>",
    re.IGNORECASE,
)

MARKDOWN_LINK_PATTERN = re.compile(
    r"(?<!!)\[([^\]\n]+)\]\(\s*([^\s)]+)([ \t]+(?:\"[^\"]*\"|'[^']*'))?\s*\)",
    re.IGNORECASE,
)

ALL_MARKDOWN_LINK_PATTERN = re.compile(
    r"(?<!!)\[[^\]\n]+\]\([^\n)]*\)",
    re.IGNORECASE,
)

PROTECTED_PATTERNS = [
    # Fenced code blocks.
    re.compile(r"(?ms)^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[ \t]*$"),

    # Inline code.
    re.compile(r"`[^`\n]+`"),

    # Markdown images.
    re.compile(
        rf"!\[[^\]\n]*\]\(\s*[^\)\n]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^\)\n]*\)",
        re.IGNORECASE,
    ),

    # Reference-style Markdown links.
    re.compile(
        rf"(?m)^[ \t]{{0,3}}\[[^\]\n]+\]:[ \t]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^\s]*.*$",
        re.IGNORECASE,
    ),

    # HTML image tags.
    re.compile(r"<img\b[\s\S]*?>", re.IGNORECASE),

    # HTML tags containing links or emails.
    # The negative lookahead prevents Markdown autolinks like <https://example.com>,
    # <mailto:name@example.com>, or <name@example.com> from being mistaken for HTML tags.
    re.compile(
        rf"<(?!https?://|www\.|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT}>)[A-Za-z][^>\n]*(?:{URL_PREFIX_PATTERN}|mailto:|{EMAIL_ADDRESS_PATTERN_TEXT})[^>\n]*>",
        re.IGNORECASE,
    ),
]


def protect_regions(
    content: str,
    patterns: list[re.Pattern],
    marker_name: str,
) -> tuple[str, list[str]]:
    """
    Replace regions we do not want to edit with temporary placeholders.
    """
    protected: list[str] = []

    def protect_match(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"@@URL_FORMATTER_{marker_name}_{len(protected) - 1}@@"

    for pattern in patterns:
        content = pattern.sub(protect_match, content)

    return content, protected


def restore_regions(content: str, protected: list[str], marker_name: str) -> str:
    """
    Restore previously protected regions.
    """
    for index, original in enumerate(protected):
        content = content.replace(
            f"@@URL_FORMATTER_{marker_name}_{index}@@",
            original,
        )

    return content


def split_trailing_punctuation(value: str) -> tuple[str, str]:
    """
    Remove punctuation that is probably sentence punctuation, not part of the URL/email.
    """
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
    """
    Return the actual web link destination.

    Bare www. links become https://www...
    Existing http:// and https:// links keep their original scheme.
    """
    if url.lower().startswith("www."):
        return f"https://{url}"

    return url


def make_web_display_text(url: str) -> str:
    """
    Return visible web link text.

    Drops only:
        - leading http://
        - leading https://
        - leading www.

    Keeps:
        - domain
        - path
        - query string
        - fragment
    """
    display_text = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    display_text = re.sub(r"^www\.", "", display_text, flags=re.IGNORECASE)

    return display_text


def make_web_markdown_link(url: str, title: str = "") -> str:
    return f"[{make_web_display_text(url)}]({make_web_href(url)}{title})"


def make_mail_href(value: str) -> str:
    """
    Return a mailto: href from either an email address or a mailto: link.
    """
    if value.lower().startswith("mailto:"):
        return value

    return f"mailto:{value}"


def make_mail_display_text(value: str) -> str:
    """
    Return visible email text.

    Drops mailto: and hides query parameters like ?subject=...
    """
    display_text = re.sub(r"^mailto:", "", value, flags=re.IGNORECASE)
    display_text = display_text.split("?", 1)[0]

    return display_text


def make_mail_markdown_link(value: str, title: str = "") -> str:
    return f"[{make_mail_display_text(value)}]({make_mail_href(value)}{title})"


def log_change(changes: list[str], original: str, formatted: str) -> None:
    """
    Log a formatting change as:
        original -> formatted
    """
    if original != formatted:
        changes.append(f"{original} -> {formatted}")


def normalize_existing_markdown_links(content: str, changes: list[str]) -> str:
    """
    Normalize existing Markdown links only when the visible text itself is a URL,
    email address, or mailto: link.

    Preserves custom labels like:
        [Department website](https://www.example.com/path)
        [Email us](mailto:name@example.com)

    Normalizes:
        [https://www.example.com/path](https://www.example.com/path)
        [www.example.com/path](https://www.example.com/path)
        [mailto:name@example.com](mailto:name@example.com)
        [name@example.com](mailto:name@example.com)
    """
    def replace_link(match: re.Match) -> str:
        label = match.group(1)
        destination = match.group(2)
        title = match.group(3) or ""

        if is_web_url_like(destination) and is_web_url_like(label):
            formatted = make_web_markdown_link(destination, title)
            log_change(changes, match.group(0), formatted)
            return formatted

        if is_mailto_like(destination) and (
            is_mailto_like(label) or is_email_like(label)
        ):
            formatted = make_mail_markdown_link(destination, title)
            log_change(changes, match.group(0), formatted)
            return formatted

        return match.group(0)

    return MARKDOWN_LINK_PATTERN.sub(replace_link, content)


def normalize_autolinks(content: str, changes: list[str]) -> str:
    """
    Convert Markdown autolinks to Markdown links.
    """
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
    """
    Convert bare web URLs to Markdown links.
    """
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
    """
    Convert bare mailto: links to Markdown links.
    """
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
    """
    Convert bare email addresses to Markdown mailto links.
    """
    def replace_email(match: re.Match) -> str:
        email = match.group(1)
        formatted = make_mail_markdown_link(email)

        log_change(changes, email, formatted)

        return formatted

    return BARE_EMAIL_PATTERN.sub(replace_email, content)


def normalize_content(content: str) -> tuple[str, list[str]]:
    """
    Normalize links in Markdown content and return:
        updated_content, changes
    """
    protected_content, protected = protect_regions(
        content,
        PROTECTED_PATTERNS,
        "PROTECTED",
    )

    changes: list[str] = []

    protected_content = normalize_existing_markdown_links(protected_content, changes)
    protected_content = normalize_autolinks(protected_content, changes)

    # Protect all existing Markdown links before converting bare URLs/mailto links,
    # so we do not rewrite hrefs inside [text](https://example.com/path).
    protected_content, markdown_links_before_bare_urls = protect_regions(
        protected_content,
        [ALL_MARKDOWN_LINK_PATTERN],
        "MARKDOWN_BEFORE_BARE_URLS",
    )

    protected_content = normalize_bare_urls(protected_content, changes)
    protected_content = normalize_bare_mailto_links(protected_content, changes)

    # Protect newly created Markdown links before converting bare emails,
    # so [name@example.com](mailto:name@example.com) does not get converted again.
    protected_content, markdown_links_before_bare_emails = protect_regions(
        protected_content,
        [ALL_MARKDOWN_LINK_PATTERN],
        "MARKDOWN_BEFORE_BARE_EMAILS",
    )

    protected_content = normalize_bare_emails(protected_content, changes)

    protected_content = restore_regions(
        protected_content,
        markdown_links_before_bare_emails,
        "MARKDOWN_BEFORE_BARE_EMAILS",
    )
    protected_content = restore_regions(
        protected_content,
        markdown_links_before_bare_urls,
        "MARKDOWN_BEFORE_BARE_URLS",
    )
    updated_content = restore_regions(
        protected_content,
        protected,
        "PROTECTED",
    )

    return updated_content, changes


def format_hyperlinks(file: str, no_save: bool = False) -> list[str]:
    """
    Format hyperlinks in a markdown file.

    Saves the file in place unless no_save=True.
    Returns a list of formatted changes.
    """
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    updated_content, changes = normalize_content(content)

    if changes and not no_save:
        with open(file, "w", encoding="utf-8") as f_out:
            f_out.write(updated_content)

    return changes


def load_files_from_content_dir(content_dir: Path) -> list[str]:
    """
    Load all .md files from the content directory and return their paths as a list.
    """
    return [str(md_file) for md_file in content_dir.rglob("*.md")]


def run_self_test() -> None:
    """
    Basic checks to make sure paths and mailto links are handled safely.
    """
    cases = {
        "Web: https://www.decyp.tas.gov.au/path/to/page":
            "Web: [decyp.tas.gov.au/path/to/page](https://www.decyp.tas.gov.au/path/to/page)",

        "Web: <https://www.decyp.tas.gov.au/path/to/page>":
            "Web: [decyp.tas.gov.au/path/to/page](https://www.decyp.tas.gov.au/path/to/page)",

        "Web: www.dss.gov.au/intercountryadoption":
            "Web: [dss.gov.au/intercountryadoption](https://www.dss.gov.au/intercountryadoption)",

        "Web: https://www.example.com/a/b?x=1#section.":
            "Web: [example.com/a/b?x=1#section](https://www.example.com/a/b?x=1#section).",

        "Web: [https://www.example.com/a/b](https://www.example.com/a/b)":
            "Web: [example.com/a/b](https://www.example.com/a/b)",

        "Web: [Custom label](https://www.example.com/a/b)":
            "Web: [Custom label](https://www.example.com/a/b)",

        "Image: ![Alt](https://www.example.com/image.png)":
            "Image: ![Alt](https://www.example.com/image.png)",

        "HTML: <img src=\"https://www.example.com/image.png\">":
            "HTML: <img src=\"https://www.example.com/image.png\">",

        "Email: user@example.com":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: mailto:user@example.com":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: <mailto:user@example.com>":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: <user@example.com>":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: mailto:user@example.com?subject=Hello":
            "Email: [user@example.com](mailto:user@example.com?subject=Hello)",

        "Email: [user@example.com](mailto:user@example.com)":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: [mailto:user@example.com](mailto:user@example.com)":
            "Email: [user@example.com](mailto:user@example.com)",

        "Email: [Contact us](mailto:user@example.com)":
            "Email: [Contact us](mailto:user@example.com)",

        "HTML: <a href=\"mailto:user@example.com\">Email</a>":
            "HTML: <a href=\"mailto:user@example.com\">Email</a>",
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
            print()

    if failed:
        sys.exit(1)

    print("Self-test passed.")


def main():
    parser = argparse.ArgumentParser(
        description="Format hyperlinks in markdown files."
    )
    parser.add_argument(
        "--root",
        default=".",
        help="site-src root, default: current directory",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save changes to files",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in tests and exit",
    )

    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return

    root = Path(args.root).resolve()
    content_dir = root / CONTENT_DIR
    
    files_changed = 0
    
    TERM_WIDTH = min(shutil.get_terminal_size((120, 20)).columns, 140)

    if not content_dir.is_dir():
        print_labeled(
            "ERROR",
            CLR_RED,
            f"Content directory not found: {display_path(content_dir, root.parent)}",
        )
        sys.exit(2)

    files = load_files_from_content_dir(content_dir)
    
    print_section("Hyperlink Format Report", TERM_WIDTH)
    print(color(f"Source:        {display_path(root, root.parent)}", CLR_WHITE))
    print(color(f"Files found:   {len(files)}", CLR_WHITE))

    for file in files:
        changes = format_hyperlinks(file, no_save=args.no_save)

        if changes:
            files_changed += 1
            print_group(
                f"Formatted hyperlinks in {display_path(file, root.parent)}",
                changes,
                "OK",
                CLR_GREEN,
            )

    if args.no_save:
        print_labeled(
            "INFO",
            CLR_YELLOW,
            "No changes were saved to files. Use without --no-save to save changes.",
        )
    else:
        if files_changed:
            print_labeled(
                "OK",
                CLR_GREEN,
                f"{files_changed} files changed.",
            )
        else:
            print_labeled(
                "OK",
                CLR_GREEN,
                "no changes needed.",
            )
        
if __name__ == "__main__":
    main()
    