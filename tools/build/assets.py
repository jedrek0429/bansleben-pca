"""Asset, image, preload, and static-copy helpers."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

import imagesize

from common import CLR_GREEN, CLR_YELLOW, print_labeled
from constants import CARD_IMAGE_VARIANT_SUFFIX, RESPONSIVE_IMAGE_SUFFIX, RESPONSIVE_IMAGE_WIDTHS, WEBP_QUALITY
from urls import asset_url

SOURCE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


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


def resized_webp_path(path: Path, width: int) -> Path:
    return path.with_name(f"{path.stem}{RESPONSIVE_IMAGE_SUFFIX.format(width=width)}.webp")


def is_generated_responsive_variant(path: Path) -> bool:
    return bool(re.search(r"-\d+w$", path.stem))


def create_webp(path: Path, output: Path, command: list[str], width: int | None = None) -> bool:
    args = [*command, str(path), "-auto-orient"]
    if width:
        args.extend(["-resize", f"{width}x>"])
    args.extend(["-quality", WEBP_QUALITY, str(output)])
    try:
        subprocess.run(
            args,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def create_responsive_webp_variants(path: Path, command: list[str]) -> None:
    try:
        original_width, _ = imagesize.get(path)
    except Exception:
        return
    if not original_width:
        return

    for width in RESPONSIVE_IMAGE_WIDTHS:
        if width >= original_width:
            continue
        output = resized_webp_path(path, width)
        if create_webp(path, output, command, width=width):
            print_labeled("OK", CLR_GREEN, f"Created {output}")
        else:
            print_labeled("WARN", CLR_YELLOW, f"error resizing {path} to {width}px.")


def has_source_sibling(path: Path) -> bool:
    return any(path.with_suffix(suffix).exists() for suffix in SOURCE_IMAGE_SUFFIXES)


def convert_to_webp(directory: str) -> None:
    command = image_magick_command()
    if not command:
        print_labeled("WARN", CLR_YELLOW, "ImageMagick not found; skipped WebP conversion.")
        return
    root = Path(directory)

    for path in root.rglob("*.*"):
        if path.suffix.lower() not in SOURCE_IMAGE_SUFFIXES:
            continue
        if is_generated_responsive_variant(path):
            continue
        webp_path = path.with_suffix(".webp")
        if create_webp(path, webp_path, command):
            print_labeled("OK", CLR_GREEN, f"Converted {path}")
        else:
            print_labeled("WARN", CLR_YELLOW, f"error converting {path}.")
        create_responsive_webp_variants(path, command)

    for path in root.rglob("*.webp"):
        if is_generated_responsive_variant(path) or has_source_sibling(path):
            continue
        create_responsive_webp_variants(path, command)


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

    high_priority_imgs = [
        img for img in re.findall(r"<img\b[^>]*>", html_without_pictures, re.IGNORECASE | re.DOTALL)
        if re.search(r'\bfetchpriority=["\']high["\']', img, re.IGNORECASE)
    ]
    for img in high_priority_imgs:
        if add(img_preload(img)):
            return preloads

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


def virtual_responsive_variant_paths(ctx, relative_path: str, suffix: str = ".webp") -> list[tuple[str, int]]:
    original = ctx.root / str(relative_path or "").lstrip("/")
    if not original.is_file():
        return []

    original_width, _ = imagesize.get(original)
    if not original_width:
        return []

    entries = []
    for width in RESPONSIVE_IMAGE_WIDTHS:
        if width >= original_width:
            continue
        rel_path = "/" + resized_webp_path(original, width).relative_to(ctx.root).as_posix()
        entries.append((rel_path, int(width)))
    return entries


def image_variant_paths(ctx, relative_path: str, suffix: str = ".webp") -> list[tuple[str, int]]:
    original = ctx.root / str(relative_path or "").lstrip("/")
    if not original.name:
        return []

    directory = original.parent
    if not directory.is_dir():
        return virtual_responsive_variant_paths(ctx, relative_path, suffix)

    original_ratio = 0.0
    if original.exists():
        width, height = imagesize.get(original)
        if width and height:
            original_ratio = width / height

    stem = original.stem
    candidates = [directory / f"{stem}{suffix}"]
    candidates.extend(sorted(directory.glob(f"{stem}-*{suffix}")))

    by_width: dict[int, str] = {}
    for path in candidates:
        if not path.is_file():
            continue
        width, height = imagesize.get(path)
        if not width or not height:
            continue
        if original_ratio and abs((width / height) - original_ratio) > 0.08:
            continue
        rel_path = "/" + path.relative_to(ctx.root).as_posix()
        by_width.setdefault(int(width), rel_path)

    for rel_path, width in virtual_responsive_variant_paths(ctx, relative_path, suffix):
        by_width.setdefault(width, rel_path)

    return [(path, width) for width, path in sorted(by_width.items())]


def responsive_image_srcset(ctx, relative_path: str, suffix: str = ".webp") -> str:
    entries = []
    for path, width in image_variant_paths(ctx, relative_path, suffix):
        entries.append(f"{asset_url(ctx, path)} {width}w")
    return ", ".join(entries)


def primary_variant_url(ctx, relative_path: str, suffix: str = ".webp") -> str:
    original = ctx.root / str(relative_path or "").lstrip("/")
    candidate = original.with_suffix(suffix)
    if candidate.is_file():
        rel_path = "/" + candidate.relative_to(ctx.root).as_posix()
        return asset_url(ctx, rel_path)
    return asset_url(ctx, str(relative_path or ""))


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
