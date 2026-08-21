"""Image URL resolution for Markdown and HTML content."""

from __future__ import annotations

import re

from image_pipeline import primary_image_url, responsive_image_srcset, source_asset_reference


CONTENT_IMAGE_SIZES = "(max-width: 940px) calc(100vw - 40px), 900px"


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


def _responsive_html_image(ctx, before_src: str, quote: str, image_path: str, after_src: str) -> str:
    reference = source_asset_reference(image_path)
    if not reference or reference not in ctx.image_manifest:
        resolved_path = resolve_content_image_path(ctx, image_path)
        return f"<img{before_src}src={quote}{resolved_path}{quote}{after_src}>"

    src = primary_image_url(ctx, reference)
    srcset = responsive_image_srcset(ctx, reference)
    attrs = after_src
    if srcset and not re.search(r"\bsrcset\s*=", attrs, re.IGNORECASE):
        attrs += f' srcset="{srcset}"'
    if srcset and not re.search(r"\bsizes\s*=", attrs, re.IGNORECASE):
        attrs += f' sizes="{CONTENT_IMAGE_SIZES}"'
    return f"<img{before_src}src={quote}{src}{quote}{attrs}>"


def resolve_images(content: str, ctx, lang: str) -> str:
    """Resolve Markdown and raw-HTML image paths for the current output mode."""

    def replace_markdown_image(match: re.Match) -> str:
        alt_text = match.group(1)
        image_path = match.group(2)
        return f"![{alt_text}]({resolve_content_image_path(ctx, image_path)})"

    def replace_html_image(match: re.Match) -> str:
        return _responsive_html_image(ctx, match.group(1), match.group(2), match.group(3), match.group(4))

    content = re.sub(r"!\[(.*?)\]\((.*?)\)", replace_markdown_image, content)
    content = re.sub(r"<img\b([^>]*?\s)src=([\'\"])(.*?)\2([^>]*)>", replace_html_image, content, flags=re.IGNORECASE)
    return content
