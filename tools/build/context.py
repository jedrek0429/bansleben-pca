"""Build context and configuration loading."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from common import display_path, load_json, load_optional_json

from constants import DEFAULT_LANGS


def normalize_url_prefix(value: str | None) -> str:
    prefix = (value or "/").strip()
    if prefix == "/":
        return ""
    return prefix.rstrip("/")


def parse_bool_env(value: str | None) -> bool:
    return (value or "0").strip().lower() not in {"0", "false", "no", "off"}


@dataclass(eq=False)
class BuildContext:
    """Shared build state passed between rendering modules.

    The class uses identity-based hashing so lru_cache can safely cache instance
    method calls per build context.
    """

    root: Path
    dist: Path | None = None
    url_prefix: str = field(default_factory=lambda: normalize_url_prefix(os.environ.get("SITE_URL_PREFIX", "/")))
    lang_in_url: bool = field(default_factory=lambda: parse_bool_env(os.environ.get("SITE_LANG_IN_URL", "0")))
    langs: list[str] = field(default_factory=list)
    pages_config: dict[str, Any] = field(default_factory=dict)
    pages_by_key: dict[str, dict[str, Any]] = field(default_factory=dict)
    cards_config: dict[str, Any] = field(default_factory=dict)
    seo_config: dict[str, Any] = field(default_factory=dict)
    hero_images: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        if self.dist is None:
            self.dist = self.root.parent / "site-dist"
        else:
            self.dist = Path(self.dist).expanduser().resolve()
        if not self.langs:
            self.langs = list(DEFAULT_LANGS)

    @classmethod
    def from_root(cls, root: str | Path) -> "BuildContext":
        return cls(root=Path(root))

    def load_locale(self, lang: str) -> dict[str, Any]:
        return load_json(self.root / "locales" / f"{lang}.json")

    def load_locales(self) -> dict[str, dict[str, Any]]:
        return {lang: self.load_locale(lang) for lang in self.langs}

    def load_configs(self) -> None:
        pages_path = self.root / "config" / "pages.json"
        cards_path = self.root / "config" / "cards.json"

        if not pages_path.exists():
            raise SystemExit(f"Missing config: {display_path(pages_path, self.root)}")

        self.pages_config = load_json(pages_path)
        configured_langs = self.pages_config.get("langs") or self.pages_config.get("languages")
        if isinstance(configured_langs, list) and configured_langs:
            self.langs = [str(lang) for lang in configured_langs]

        self.pages_by_key = {
            page["key"]: page
            for page in self.pages_config.get("pages", [])
            if isinstance(page, dict) and page.get("key")
        }
        self.cards_config = load_json(cards_path) if cards_path.exists() else {}
        self.seo_config = load_optional_json(self.root / "config" / "seo.json")
        self.hero_images = load_optional_json(self.root / "config" / "hero_images.json")
        self.clear_caches()

    def clear_caches(self) -> None:
        self.content_path_for.cache_clear()
        self.read_markdown.cache_clear()
        self.image_info.cache_clear()

    @lru_cache(maxsize=None)
    def content_path_for(self, lang: str, key: str) -> Path | None:
        candidates = [
            self.root / "content" / lang / f"{key}.md",
            self.root / "content" / "en" / f"{key}.md",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    @lru_cache(maxsize=None)
    def read_markdown(self, lang: str, key: str) -> str:
        path = self.content_path_for(lang, key)
        if not path:
            return ""
        return path.read_text(encoding="utf-8")

    @lru_cache(maxsize=None)
    def image_info(self, relative_path: str) -> dict[str, str | int]:
        import imagesize

        value = str(relative_path or "")
        if not value:
            return {"width": "", "height": "", "webp_src": ""}

        full_path = self.root / value.lstrip("/")
        if full_path.exists():
            width, height = imagesize.get(full_path)
            return {
                "width": width,
                "height": height,
                "webp_src": value.rsplit(".", 1)[0] + ".webp" if "." in value else value,
            }
        return {"width": "", "height": "", "webp_src": value}
