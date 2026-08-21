"""Build context and configuration loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from common import display_path, load_json, load_optional_json


def normalize_url_prefix(value: str | None) -> str:
    prefix = (value or "/").strip()
    if prefix == "/":
        return ""
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix
    return prefix.rstrip("/")


def parse_bool_env(value: str | None) -> bool:
    return (value or "0").strip().lower() not in {"0", "false", "no", "off"}


def parse_langs(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def ordered_codes(paths) -> list[str]:
    codes = sorted(path.stem for path in paths if path.is_file())
    if "en" in codes:
        codes.remove("en")
        codes.insert(0, "en")
    return codes


@dataclass(eq=False)
class BuildContext:
    """Shared build state and resolved per-site structural configuration."""

    root: Path
    dist: Path | None = None
    url_prefix: str = field(default_factory=lambda: normalize_url_prefix(os.environ.get("SITE_URL_PREFIX", "/")))
    lang_in_url: bool = field(default_factory=lambda: parse_bool_env(os.environ.get("SITE_LANG_IN_URL", "0")))
    langs: list[str] = field(default_factory=list)
    pages_config: dict[str, Any] = field(default_factory=dict)
    pages_by_key: dict[str, dict[str, Any]] = field(default_factory=dict)
    site_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    cards_config: dict[str, Any] = field(default_factory=dict)
    seo_config: dict[str, Any] = field(default_factory=dict)
    hero_images: dict[str, Any] = field(default_factory=dict)
    image_manifest: dict[str, dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        self.dist = self.root.parent / "site-dist" if self.dist is None else Path(self.dist).expanduser().resolve()
        self.url_prefix = normalize_url_prefix(self.url_prefix)
        self.langs = parse_langs(self.langs)

    @classmethod
    def from_root(cls, root: str | Path, *, dist: str | Path | None = None, url_prefix: str | None = None,
                  lang_in_url: bool | None = None, langs: str | list[str] | None = None) -> "BuildContext":
        kwargs = {"root": Path(root)}
        if dist is not None:
            kwargs["dist"] = Path(dist)
        if url_prefix is not None:
            kwargs["url_prefix"] = normalize_url_prefix(url_prefix)
        if lang_in_url is not None:
            kwargs["lang_in_url"] = bool(lang_in_url)
        parsed_langs = parse_langs(langs)
        if parsed_langs:
            kwargs["langs"] = parsed_langs
        return cls(**kwargs)

    def load_locale(self, lang: str) -> dict[str, Any]:
        return load_json(self.root / "locales" / f"{lang}.json")

    def load_locales(self) -> dict[str, dict[str, Any]]:
        locales = {lang: self.load_locale(lang) for lang in self.langs}
        self._apply_locale_seo(locales)
        return locales

    def _apply_locale_seo(self, locales: dict[str, dict[str, Any]]) -> None:
        """Overlay locale-owned SEO values onto the legacy shared maps.

        Existing locales remain compatible with config/seo.json. New sites can
        provide all translated SEO values inside their locale file and require
        no edit to shared SEO configuration.
        """
        for lang, locale in locales.items():
            seo = locale.get("seo", {}) if isinstance(locale, dict) else {}
            if not isinstance(seo, dict):
                continue
            scalar_maps = {
                "hreflang": "hreflang",
                "og_locale": "og_locale",
                "social_image": "social_images",
                "default_description": "default_descriptions",
            }
            for source_key, target_key in scalar_maps.items():
                value = seo.get(source_key)
                if value is not None:
                    self.seo_config.setdefault(target_key, {})[lang] = value
            descriptions = seo.get("descriptions", {})
            if isinstance(descriptions, dict):
                target = self.seo_config.setdefault("descriptions", {})
                for key, value in descriptions.items():
                    target.setdefault(key, {})[lang] = value

    def load_configs(self) -> None:
        pages_path = self.root / "config" / "pages.json"
        if not pages_path.exists():
            raise SystemExit(f"Missing config: {display_path(pages_path, self.root)}")
        self.pages_config = load_json(pages_path)
        self.pages_by_key = {
            page["key"]: page
            for page in self.pages_config.get("pages", [])
            if isinstance(page, dict) and page.get("key")
        }

        sites_dir = self.root / "sites"
        site_paths = list(sites_dir.glob("*.json")) if sites_dir.is_dir() else []
        if not self.langs:
            self.langs = ordered_codes(site_paths)
            if not self.langs:
                self.langs = ordered_codes((self.root / "locales").glob("*.json"))
        if not self.langs:
            raise SystemExit("No site/locale definitions found")

        self.site_configs = {}
        for lang in self.langs:
            path = sites_dir / f"{lang}.json"
            self.site_configs[lang] = load_optional_json(path) if path.exists() else {}

        cards_path = self.root / "config" / "cards.json"
        self.cards_config = load_json(cards_path) if cards_path.exists() else {}
        self.seo_config = load_optional_json(self.root / "config" / "seo.json")
        self.hero_images = load_optional_json(self.root / "config" / "hero_images.json")
        self.image_manifest = {}
        self.clear_caches()

    def effective_pages(self, lang: str) -> list[dict[str, Any]]:
        """Return shared pages plus structural pages owned only by one site."""
        pages = [dict(page) for page in self.pages_config.get("pages", []) if isinstance(page, dict)]
        extra = self.site_configs.get(lang, {}).get("extra_pages", [])
        if isinstance(extra, dict):
            extra = [{"key": key, **value} for key, value in extra.items() if isinstance(value, dict)]
        if isinstance(extra, list):
            pages.extend(dict(page) for page in extra if isinstance(page, dict) and page.get("key"))
        return pages

    def page_config(self, lang: str, key: str) -> dict[str, Any]:
        shared = self.pages_by_key.get(key)
        if shared:
            return shared
        for page in self.effective_pages(lang):
            if page.get("key") == key:
                return page
        return {}

    def clear_caches(self) -> None:
        self.content_path_for.cache_clear()
        self.read_markdown.cache_clear()
        self.image_info.cache_clear()

    @lru_cache(maxsize=None)
    def content_path_for(self, lang: str, key: str) -> Path | None:
        path = self.root / "content" / lang / f"{key}.md"
        return path if path.exists() else None

    @lru_cache(maxsize=None)
    def read_markdown(self, lang: str, key: str) -> str:
        path = self.content_path_for(lang, key)
        return path.read_text(encoding="utf-8") if path else ""

    @lru_cache(maxsize=None)
    def image_info(self, relative_path: str) -> dict[str, str | int]:
        import imagesize
        value = str(relative_path or "")
        if not value:
            return {"width": "", "height": "", "webp_src": ""}
        full_path = self.root / value.lstrip("/")
        if full_path.exists():
            width, height = imagesize.get(full_path)
            return {"width": width, "height": height,
                    "webp_src": value.rsplit(".", 1)[0] + ".webp" if "." in value else value}
        return {"width": "", "height": "", "webp_src": value}
