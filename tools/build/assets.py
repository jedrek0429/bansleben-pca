"""Asset, image, preload, and static-copy helpers."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

from common import CLR_GREEN, CLR_YELLOW, print_labeled
from constants import CARD_IMAGE_VARIANT_SUFFIX, WEBP_QUALITY
from urls import asset_url


def image_300_variant(src: str) -> str:
    """Return the expected 300x200 image variant path for a source image path."""
    match = re.match(r"^(.*?)(\.[a-zA-Z0-9]+)$", src)
    if not match:
        return src
    return f"{match.group(1)}{CARD_IMAGE_VARIANT_SUFFIX}{match.group(2)}"


def image_magick_command() -> list[str] | None:
    """Return an available ImageMagick command, supporting both modern and legacy installs."""
    magick = shutil.which("magick")
    if magick:
        return [magick]

    convert = shutil.which("convert")
    if convert:
        return [convert]

    return None


def convert_to_webp(directory: str) -> None:
    """Convert PNG/JPEG files in a directory tree to WebP when ImageMagick is available."""
    command = image_magick_command()
    if not command:
        print_labeled("WARN", CLR_YELLOW, "ImageMagick not found; skipped WebP conversion.")
        return

    for path in Path(directory).rglob("*.*"):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue

        webp_path = path.with_suffix(".webp")
        if webp_path.exists():
            continue

        try:
            subprocess.run(
                [*command, str(path), "-quality", WEBP_QUALITY, str(webp_path)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print_labeled("OK", CLR_GREEN, f"Converted {path}")
        except subprocess.CalledProcessError:
            print_labeled("WARN", CLR_YELLOW, f"error converting {path}.")


def first_srcset_url(srcset: str) -> str:
    """Return the first URL from a srcset value."""
    first_candidate = srcset.split(",", 1)[0].strip()
    return first_candidate.split(None, 1)[0] if first_candidate else ""


def find_images_to_preload(html_text: str) -> list[str]:
    """Find image URLs worth preloading, deduplicating while preserving order."""
    patterns = [
        (r'<img[^>]*\bsrc=["\']([^"\']+)["\']', lambda value: value),
        (r'<source[^>]*\bsrcset=["\']([^"\']+)["\']', first_srcset_url),
    ]

    images = []
    seen = set()

    for pattern, normalize in patterns:
        for match in re.findall(pattern, html_text, re.IGNORECASE):
            image = normalize(match).strip()
            if image and image not in seen:
                seen.add(image)
                images.append(image)

    return images


def render_preload(images: list[str]) -> str:
    """Render preload links for a list of image URLs."""
    return "\n".join(
        f'<link rel="preload" href="{html.escape(img, quote=True)}" as="image" fetchpriority="high">'
        for img in images
    )


def copy_path(src: Path, dst: Path) -> None:
    """Copy a file or directory to the destination, creating parent directories when needed."""
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    elif src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def copy_assets_to(ctx, dst: Path) -> None:
    assets_src = ctx.root / "assets"
    assets_dst = dst / "assets"

    if assets_src.exists():
        for item in assets_src.iterdir():
            if item.name == "common":
                continue
            copy_path(item, assets_dst / item.name)


def copy_static(ctx, lang: str) -> None:
    """Copy public PHP files, private contact config, and language-local assets."""
    lang_root = ctx.dist / lang
    lang_root.mkdir(parents=True, exist_ok=True)

    # Assets are copied into each language root in all modes so generated URLs like
    # /en/assets/... and /preview-prefix/en/assets/... always resolve.
    copy_assets_to(ctx, lang_root)

    for php_src in ctx.root.glob("*.php"):
        if php_src.name == "pca-contact-config.php":
            continue
        copy_path(php_src, lang_root / php_src.name)

    config_src = ctx.root / "pca-contact-config.json"
    private_dir = lang_root / ".private"

    if ctx.lang_in_url:
        private_dir = ctx.dist / ".private"

    private_dir.mkdir(parents=True, exist_ok=True)

    if config_src.exists():
        copy_path(config_src, private_dir / "pca-contact-config.json")

    (private_dir / ".htaccess").write_text("Require all denied\n", encoding="utf-8")


def get_image_info(ctx, relative_path: str) -> dict:
    return dict(ctx.image_info(str(relative_path or "")))


def asset_url_for(ctx, path: str) -> str:
    return asset_url(ctx, path)
