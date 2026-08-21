"""Deterministic responsive-image generation for build output.

Source-controlled files under assets/ are immutable inputs. Optimised image
renditions are generated into the disposable build tree and described by an
in-memory manifest consumed by the renderers.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import imagesize

from assets import image_magick_command
from common import CLR_GREEN, print_labeled
from constants import RESPONSIVE_IMAGE_WIDTHS, WEBP_QUALITY
from urls import asset_url

SUPPORTED_SOURCE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GENERATED_IMAGE_DIR = "_generated/images"
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
HTML_IMAGE_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)


def source_asset_reference(value: str) -> str | None:
    """Resolve a local content image path to its canonical source asset path."""
    path = str(value or "").strip()
    if not path or path.startswith(("http://", "https://", "//", "data:", "mailto:", "#")):
        return None
    if path.startswith("/assets/"):
        reference = path
    elif path.startswith("assets/"):
        reference = "/" + path
    else:
        reference = "/assets/" + path.lstrip("/")
    return reference if Path(reference).suffix.lower() in SUPPORTED_SOURCE_SUFFIXES else None


def _walk_asset_references(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_asset_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_asset_references(child)
    elif isinstance(value, str):
        reference = source_asset_reference(value) if value.strip().startswith(("/assets/", "assets/")) else None
        if reference:
            yield reference


def _content_image_references(ctx) -> set[str]:
    refs: set[str] = set()
    for lang in ctx.langs:
        content_dir = ctx.root / "content" / lang
        if not content_dir.is_dir():
            continue
        for path in sorted(content_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            for match in MARKDOWN_IMAGE_RE.finditer(text):
                raw = match.group(1).strip().split(None, 1)[0].strip("<>")
                reference = source_asset_reference(raw)
                if reference:
                    refs.add(reference)
            for match in HTML_IMAGE_RE.finditer(text):
                reference = source_asset_reference(match.group(1))
                if reference:
                    refs.add(reference)
    return refs


def collect_referenced_images(ctx, locales) -> list[str]:
    """Return local raster images referenced by configuration or content."""
    refs = set(_walk_asset_references(locales))
    refs.update(_walk_asset_references(ctx.hero_images))
    refs.update(_content_image_references(ctx))
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


def _generate_variant(
    source: Path,
    destination: Path,
    command: list[str],
    width: int,
) -> None:
    args = [*command, str(source), "-auto-orient", "-resize", f"{width}x>", "-quality", str(WEBP_QUALITY), str(destination)]
    completed = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"ImageMagick failed for {source.name} at {width}px: {detail}")


def _generate_variants(source: Path, output_dir: Path, digest: str, command: list[str]) -> dict[str, Any]:
    original_width, original_height = imagesize.get(source)
    if not original_width or not original_height:
        raise ValueError(f"Image has invalid dimensions: {source}")

    variants = []
    for width in _target_widths(int(original_width)):
        height = round(int(original_height) * width / int(original_width))
        filename = f"{digest}-{width}w.webp"
        destination = output_dir / filename
        _generate_variant(source, destination, command, width)
        variants.append({
            "width": width,
            "height": height,
            "path": f"/{GENERATED_IMAGE_DIR}/{filename}",
        })

    return {
        "width": int(original_width),
        "height": int(original_height),
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
    command = image_magick_command()
    if not command:
        raise SystemExit("ImageMagick is required to build responsive images; install 'magick' or 'convert'.")

    output_dir = _generated_output_root(ctx)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict[str, Any]] = {}

    for reference in collect_referenced_images(ctx, locales):
        source = ctx.root / reference.lstrip("/")
        if not source.is_file():
            continue
        digest = _content_digest(source)
        manifest[reference] = _generate_variants(source, output_dir, digest, command)

    _copy_generated_for_production(ctx, output_dir)
    print_labeled("OK", CLR_GREEN, f"generated responsive images for {len(manifest)} referenced sources.")
    return manifest


def primary_image_url(ctx, source: str) -> str:
    reference = source_asset_reference(source) or str(source or "")
    entry = ctx.image_manifest.get(reference, {})
    primary = entry.get("primary") if isinstance(entry, dict) else None
    return asset_url(ctx, str(primary or source or ""))


def responsive_image_srcset(ctx, source: str) -> str:
    reference = source_asset_reference(source) or str(source or "")
    entry = ctx.image_manifest.get(reference, {})
    variants = entry.get("variants", []) if isinstance(entry, dict) else []
    if not isinstance(variants, list):
        return ""
    return ", ".join(
        f"{asset_url(ctx, str(variant['path']))} {int(variant['width'])}w"
        for variant in variants
        if isinstance(variant, dict) and variant.get("path") and variant.get("width")
    )
