"""Deterministic responsive-image generation for build output.

Source-controlled files under assets/ are immutable inputs. Optimised image
renditions are generated into the disposable build tree and described by an
in-memory manifest consumed by the renderers.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from common import CLR_GREEN, print_labeled
from constants import RESPONSIVE_IMAGE_WIDTHS, WEBP_QUALITY
from urls import asset_url

SUPPORTED_SOURCE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GENERATED_IMAGE_DIR = "_generated/images"


def _walk_asset_references(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_asset_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_asset_references(child)
    elif isinstance(value, str):
        path = value.strip()
        if path.startswith("/assets/") and Path(path).suffix.lower() in SUPPORTED_SOURCE_SUFFIXES:
            yield path


def collect_referenced_images(ctx, locales) -> list[str]:
    """Return local raster images referenced by builder-managed configuration."""
    refs = set(_walk_asset_references(locales))
    refs.update(_walk_asset_references(ctx.hero_images))
    return sorted(refs)


def _content_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _target_widths(original_width: int) -> list[int]:
    max_width = max(RESPONSIVE_IMAGE_WIDTHS)
    capped_width = min(original_width, max_width)
    widths = {width for width in RESPONSIVE_IMAGE_WIDTHS if width < capped_width}
    widths.add(capped_width)
    return sorted(widths)


def _prepare_image(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        return image.convert("RGBA")
    return image.convert("RGB")


def _generate_variants(source: Path, output_dir: Path, digest: str) -> dict[str, Any]:
    with Image.open(source) as opened:
        image = _prepare_image(opened)
        original_width, original_height = image.size
        if not original_width or not original_height:
            raise ValueError(f"Image has invalid dimensions: {source}")

        variants = []
        quality = int(WEBP_QUALITY)
        for width in _target_widths(original_width):
            height = round(original_height * width / original_width)
            resized = image if width == original_width else image.resize((width, height), Image.Resampling.LANCZOS)
            filename = f"{digest}-{width}w.webp"
            destination = output_dir / filename
            resized.save(destination, "WEBP", quality=quality, method=6)
            variants.append({
                "width": width,
                "height": height,
                "path": f"/{GENERATED_IMAGE_DIR}/{filename}",
            })

    return {
        "width": original_width,
        "height": original_height,
        "variants": variants,
        "primary": variants[-1]["path"],
    }


def _generated_output_root(ctx) -> Path:
    if ctx.lang_in_url:
        return ctx.dist / GENERATED_IMAGE_DIR
    if not ctx.langs:
        return ctx.dist / GENERATED_IMAGE_DIR
    return ctx.dist / ctx.langs[0] / GENERATED_IMAGE_DIR


def _copy_generated_for_production(ctx, generated_root: Path) -> None:
    if ctx.lang_in_url or len(ctx.langs) < 2:
        return
    source_root = generated_root.parent
    for lang in ctx.langs[1:]:
        destination = ctx.dist / lang / "_generated"
        shutil.copytree(source_root, destination, dirs_exist_ok=True)


def build_image_manifest(ctx, locales) -> dict[str, dict[str, Any]]:
    """Generate responsive WebP renditions and return their manifest.

    Missing source files are deliberately left for the generated-output asset
    validator to report against the HTML that actually references them.
    """
    output_dir = _generated_output_root(ctx)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, Any]] = {}

    for reference in collect_referenced_images(ctx, locales):
        source = ctx.root / reference.lstrip("/")
        if not source.is_file():
            continue
        digest = _content_digest(source)
        manifest[reference] = _generate_variants(source, output_dir, digest)

    _copy_generated_for_production(ctx, output_dir)
    print_labeled("OK", CLR_GREEN, f"generated responsive images for {len(manifest)} referenced sources.")
    return manifest


def primary_image_url(ctx, source: str) -> str:
    entry = ctx.image_manifest.get(str(source or ""), {})
    primary = entry.get("primary") if isinstance(entry, dict) else None
    return asset_url(ctx, str(primary or source or ""))


def responsive_image_srcset(ctx, source: str) -> str:
    entry = ctx.image_manifest.get(str(source or ""), {})
    variants = entry.get("variants", []) if isinstance(entry, dict) else []
    if not isinstance(variants, list):
        return ""
    return ", ".join(
        f"{asset_url(ctx, str(variant['path']))} {int(variant['width'])}w"
        for variant in variants
        if isinstance(variant, dict) and variant.get("path") and variant.get("width")
    )
