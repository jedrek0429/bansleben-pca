"""Image URL resolution for Markdown and HTML content."""

from __future__ import annotations

import re


def is_absolute_or_special_path(path: str) -> bool:
    value = str(path or "")
    return value.startswith(("http://", "https://", "//", "data:", "mailto:", "#"))


def join_paths(base_path: str, image_path: str) -> str:
    return f"{base_path.rstrip('/')}/{image_path.lstrip('/')}"


def content_asset_base(ctx) -> str:
    """Return the public asset base for content images."""
    return f"{ctx.url_prefix}/assets" if ctx.url_prefix else "/assets"


def resolve_content_image_path(ctx, image_path: str) -> str:
    value = str(image_path or "")
    if is_absolute_or_special_path(value):
        return value
    if value.startswith("/assets/"):
        value = value[len("/assets/"):]
    elif value.startswith("assets/"):
        value = value[len("assets/"):]
    return join_paths(content_asset_base(ctx), value)


def resolve_images(content: str, ctx, lang: str) -> str:
    """Resolve Markdown image and HTML img src paths for the current output mode."""

    def replace_markdown_image(match: re.Match) -> str:
        alt_text = match.group(1)
        image_path = match.group(2)
        return f"![{alt_text}]({resolve_content_image_path(ctx, image_path)})"

    def replace_html_image(match: re.Match) -> str:
        before_src = match.group(1)
        quote = match.group(2)
        image_path = match.group(3)
        after_src = match.group(4)
        resolved_path = resolve_content_image_path(ctx, image_path)
        return f"<img{before_src}src={quote}{resolved_path}{quote}{after_src}>"

    content = re.sub(r"!\[(.*?)\]\((.*?)\)", replace_markdown_image, content)
    content = re.sub(r"<img\b([^>]*?\s)src=([\'\"])(.*?)\2([^>]*)>", replace_html_image, content, flags=re.IGNORECASE)
    return content
