import re


def is_absolute_or_special_path(path: str) -> bool:
    """
    Return True if the path should not be modified.
    """
    return (
        path.startswith("http://")
        or path.startswith("https://")
        or path.startswith("//")
        or path.startswith("data:")
        or path.startswith("mailto:")
        or path.startswith("#")
    )


def join_paths(base_path: str, image_path: str) -> str:
    """
    Join base path and image path without creating duplicate slashes.
    """
    return f"{base_path.rstrip('/')}/{image_path.lstrip('/')}"


def resolve_images(content: str, base_path: str) -> str:
    """
    Resolve Markdown image paths and HTML <img src="..."> paths.

    Examples:
        ![Alt](image.png)
        -> ![Alt](/base/image.png)

        <img src="image.png" alt="Alt">
        -> <img src="/base/image.png" alt="Alt">
    """

    def replace_markdown_image(match: re.Match) -> str:
        alt_text = match.group(1)
        image_path = match.group(2)

        if is_absolute_or_special_path(image_path):
            return match.group(0)

        resolved_path = join_paths(base_path, image_path)
        return f"![{alt_text}]({resolved_path})"

    def replace_html_image(match: re.Match) -> str:
        before_src = match.group(1)
        quote = match.group(2)
        image_path = match.group(3)
        after_src = match.group(4)

        if is_absolute_or_special_path(image_path):
            return match.group(0)

        resolved_path = join_paths(base_path, image_path)
        return f"<img{before_src}src={quote}{resolved_path}{quote}{after_src}>"

    markdown_image_pattern = r"!\[(.*?)\]\((.*?)\)"

    html_image_pattern = re.compile(
        r"<img\b([^>]*?\s)src=(['\"])(.*?)\2([^>]*)>",
        re.IGNORECASE,
    )

    content = re.sub(markdown_image_pattern, replace_markdown_image, content)
    content = re.sub(html_image_pattern, replace_html_image, content)

    return content
