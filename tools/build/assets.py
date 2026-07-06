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
    match = re.match(r"^(.*?)(\.[a-zA-Z0-9]+)$", src)
    if not match:
        return src
    return f"{match.group(1)}{CARD_IMAGE_VARIANT_SUFFIX}{match.group(2)}"


def image_magick_command() -> list[str] | None:
    magick = shutil.which("magick")
    if magick:
        return [magick]
    convert = shutil.which("convert")
    if convert:
        return [convert]
    return None


def convert_to_webp(directory: str) -> None:
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
    first_candidate = srcset.split(",", 1)[0].strip()
    return first_candidate.split(None, 1)[0] if first_candidate else ""


def attr_value(attrs: str, name: str) -> str:
    match = re.search(rf'\b{name}=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def image_preload(src: str = "", srcset: str = "", sizes: str = "") -> dict[str, str]:
    href = first_srcset_url(srcset) if srcset else src.strip()
    preload = {"href": href}
    if srcset:
        preload["imagesrcset"] = srcset.strip()
    if sizes:
        preload["imagesizes"] = sizes.strip()
    return preload


def img_preload(img_tag: str) -> dict[str, str]:
    src = attr_value(img_tag, "src")
    srcset = attr_value(img_tag, "srcset")
    sizes = attr_value(img_tag, "sizes")
    return image_preload(src, srcset, sizes)


def source_preload(source_tag: str) -> dict[str, str]:
    srcset = attr_value(source_tag, "srcset")
    sizes = attr_value(source_tag, "sizes")
    return image_preload(srcset=srcset, sizes=sizes)


def best_picture_preload(picture_html: str) -> dict[str, str]:
    sources = re.findall(r"<source\b[^>]*>", picture_html, re.IGNORECASE | re.DOTALL)
    preferred = [
        source for source in sources
        if re.search(r'\btype=["\']image/(?:avif|webp)["\']', source, re.IGNORECASE)
    ]
    for source in [*preferred, *sources]:
        preload = source_preload(source)
        if preload.get("href"):
            return preload
    img = re.search(r"<img\b[^>]*>", picture_html, re.IGNORECASE | re.DOTALL)
    return img_preload(img.group(0)) if img else {}


def find_images_to_preload(html_text: str, limit: int = 1) -> list[dict[str, str]]:
    picture_pattern = re.compile(r"<picture\b[^>]*>.*?</picture>", re.IGNORECASE | re.DOTALL)
    pictures = picture_pattern.findall(html_text)
    html_without_pictures = picture_pattern.sub("", html_text)

    preloads = []
    seen = set()

    def add(preload: dict[str, str]) -> bool:
        href = preload.get("href", "").strip()
        if not href:
            return False
        key = (href, preload.get("imagesrcset", ""), preload.get("imagesizes", ""))
        if key in seen:
            return False
        seen.add(key)
        preloads.append(preload)
        return len(preloads) >= limit

    for picture in pictures:
        if add(best_picture_preload(picture)):
            return preloads

    for img in re.findall(r"<img\b[^>]*>", html_without_pictures, re.IGNORECASE | re.DOTALL):
        if add(img_preload(img)):
            return preloads

    return preloads


def render_preload(images: list[dict[str, str]]) -> str:
    links = []
    for image in images:
        attrs = [
            'rel="preload"',
            f'href="{html.escape(image["href"], quote=True)}"',
            'as="image"',
        ]
        if image.get("imagesrcset"):
            attrs.append(f'imagesrcset="{html.escape(image["imagesrcset"], quote=True)}"')
        if image.get("imagesizes"):
            attrs.append(f'imagesizes="{html.escape(image["imagesizes"], quote=True)}"')
        attrs.append('fetchpriority="high"')
        links.append("<link " + " ".join(attrs) + ">")
    return "\n".join(links)


def copy_path(src: Path, dst: Path) -> None:
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
    lang_root = ctx.dist / lang
    lang_root.mkdir(parents=True, exist_ok=True)
    if ctx.lang_in_url:
        copy_assets_to(ctx, ctx.dist)
    else:
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
