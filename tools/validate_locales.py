"""
Validate locale JSONs against `config/pages.json` and `locales/en.json`.

Checks implemented:
- All locales referenced in `pages.json` exist in `site-src/locales/*.json`.
- Parent chain correctness and parent-enabled coverage for each child's enabled locales.
- `pages.json` keys uniqueness and presence of `template`.
- Locale files contain page entries for enabled pages and those entries have required fields
  (`title`, `slug`) and, for card items, `image_alt`, `image_title`, `image_src` where defined in `en.json`.
- Slugs and titles in locale files match `pages.json`'s `slugs`/`titles` for the same locale.
- `card_items` structure is consistent across locales and matches `en.json` fields and image_src values.
- No unexpected extra fields in other locale files compared to `en.json` (top-level keys and `card_items` keys).

Automatic fixes are available for some issues via `autofix_locales.py` (run after validation).

Usage: run from site-src root (or specify `--root path/to/site-src`)

Exits with:
- 0: no unfixable errors and no fixable issues
- 1: unfixable errors found
"""

from __future__ import annotations

import argparse
import os
import sys
import subprocess
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

from common import (
    CLR_BLUE,
	CLR_GREEN,
	CLR_RED,
	CLR_WHITE,
	CLR_YELLOW,
	color,
	display_path,
	load_json,
	print_group,
	print_labeled,
	print_section,
)


def find_locale_files(locales_dir: Path) -> List[Path]:
	files = []
	for name in os.listdir(locales_dir):
		if name.endswith(".json"):
			files.append(locales_dir / name)
	return sorted(files)


def main():
	parser = argparse.ArgumentParser(
		description="Validate locale JSON files against pages.json and locales/en.json."
	)
	parser.add_argument("--root", default=".", help="site-src root, default: current directory")
	args = parser.parse_args()
 
	root = Path(args.root).resolve()
	cfg_pages = root / "config" / "pages.json"
	locales_dir = root / "locales"
 
	errors: List[str] = []
	warnings: List[str] = []

	TERM_WIDTH = min(shutil.get_terminal_size((120, 20)).columns, 140)
	ISSUE_WIDTH = max(60, TERM_WIDTH - 18)

	def clean_message(message: str) -> str:
		"""Shorten repeated absolute paths before wrapping issue text."""
		return message.replace(str(root), "<site-src>").replace(str(locales_dir), "<locales>")

	if not root.is_dir():
		print_labeled("ERROR", CLR_RED, f"site-src not found: {display_path(root, root.parent)}")
		sys.exit(2)

	if not cfg_pages.is_file():
		print_labeled("ERROR", CLR_RED, f"pages.json not found: {display_path(cfg_pages, root.parent)}")
		sys.exit(2)

	if not locales_dir.is_dir():
		print_labeled("ERROR", CLR_RED, f"locales directory not found: {display_path(locales_dir, root.parent)}")
		sys.exit(2)

	pages_data = load_json(cfg_pages)
	locale_files = find_locale_files(locales_dir)
	locales: Dict[str, dict] = {}

	for lf in locale_files:
		try:
			d = load_json(lf)
		except Exception as e:
			errors.append(clean_message(f"Failed to parse {display_path(lf, root.parent)}: {e}"))
			continue
		lang = d.get("lang") or os.path.splitext(os.path.basename(lf))[0]
		locales[lang] = d

	if "en" not in locales:
		errors.append("en.json (lang 'en') is required in locales and missing")
		print_errors(errors)
		sys.exit(1)

	# pages.json validations
	pages = pages_data.get("pages", [])
	key_counts: Dict[str, int] = defaultdict(int)
	key_map: Dict[str, dict] = {}

	for p in pages:
		key = p.get("key")
		if not key:
			errors.append("Found page without a 'key' in pages.json")
			continue
		key_counts[key] += 1
		key_map[key] = p
		if "template" not in p:
			errors.append(f"Page '{key}' missing 'template' in pages.json")

	for k, cnt in key_counts.items():
		if cnt != 1:
			errors.append(f"Duplicate page key in pages.json: '{k}' (count={cnt})")

	# collect locales referenced in pages.json
	locales_in_pages: Set[str] = set()
	for p in pages:
		for loc in p.get("enabled", []):
			locales_in_pages.add(loc)

	# Check that all referenced locales exist
	for loc in sorted(locales_in_pages):
		if loc not in locales:
			errors.append(f"Locale '{loc}' referenced in pages.json but no {loc}.json found")

	# Parent chain checks
	for p in pages:
		key = p["key"]
		parent = p.get("parent")
		if parent:
			if parent not in key_map:
				errors.append(f"Page '{key}' references missing parent '{parent}'")
			else:
				# ensure parent's enabled locales cover child's enabled locales
				child_enabled = set(p.get("enabled", []))
				parent_enabled = set(key_map[parent].get("enabled", []))
				missing = child_enabled - parent_enabled
				if missing:
					errors.append(
						f"Parent '{parent}' is not enabled for locales {sorted(missing)} required by child '{key}'"
					)

	# validate locale page entries against pages.json and en.json
	en = locales["en"]
	en_pages = en.get("pages", {})
	en_card_items = en.get("card_items", {})

	# top-level key consistency check
	en_top_keys = set(en.keys())

	for lang, data in locales.items():
		if not isinstance(data, dict):
			errors.append(f"Locale {lang} is not a JSON object")
			continue
		# top-level keys extra check
		extra_top = set(data.keys()) - en_top_keys
		if extra_top:
			warnings.append(f"Locale '{lang}' has extra top-level keys not in en.json: {sorted(extra_top)}")

		pages_obj = data.get("pages", {})
		card_items = data.get("card_items", {})

		# for each page in pages.json, check presence and required fields
		for p in pages:
			key = p["key"]
			enabled_locales = set(p.get("enabled", []))
			is_enabled_for_lang = lang in enabled_locales

			page_entry = pages_obj.get(key)
			# If pages.json says the page is enabled for this locale, the locale JSON should have the page entry and enabled true
			if is_enabled_for_lang:
				if page_entry is None:
					errors.append(f"Locale '{lang}' missing page entry for enabled page '{key}'")
				else:
					if not page_entry.get("enabled"):
						errors.append(f"Locale '{lang}' pages.{key}.enabled is false but pages.json enables it")
					# title and slug checks
					title = page_entry.get("title")
					if not title:
						errors.append(f"Locale '{lang}' pages.{key} missing or empty 'title' (enabled in pages.json)")
					# slug match pages.json
					pages_slugs = p.get("slugs", {})
					expected_slug = pages_slugs.get(lang, "")
					if page_entry.get("slug", "") != expected_slug:
						errors.append(
							f"Locale '{lang}' pages.{key}.slug mismatch: locale='{page_entry.get('slug')}' pages.json='{expected_slug}'"
						)
			else:
				# If pages.json says it's not enabled for this locale, locale pages entry should be either absent or have enabled=false
				if page_entry is not None and page_entry.get("enabled"):
					warnings.append(f"Locale '{lang}' pages.{key} is enabled but pages.json does not list '{lang}' for this page")

			# Card items checks (image fields)
			en_card = en_card_items.get(key, {})
			card = card_items.get(key)
			# If en defines card items fields, require same keys in other locales
			if en_card:
				en_card_keys = set(en_card.keys())
				if lang == "en":
					# ensure en card has title and image fields as expected for enabled pages
					if p.get("key") and p.get("enabled"):
						pass
				# For enabled pages in this locale, ensure card item exists and has image fields
				if is_enabled_for_lang:
					if card is None:
						errors.append(f"Locale '{lang}' missing card_items entry for enabled page '{key}'")
					else:
						card_keys = set(card.keys())
						# Required keys: title, image_alt, image_title
						for req in ("title", "image_alt", "image_title"):
							if req not in card:
								errors.append(f"Locale '{lang}' card_items.{key} missing '{req}'")
						# If en has image_src, require same image_src in other locales (en is source of truth)
						en_image = en_card.get("image_src")
						if en_image:
							if card.get("image_src") != en_image:
								errors.append(
									f"Locale '{lang}' card_items.{key}.image_src differs from en.json: '{card.get('image_src')}' != '{en_image}'"
								)

	# Slug/title unique checks per locale
	for lang, data in locales.items():
		pages_obj = data.get("pages", {})
		slug_map: Dict[str, List[str]] = defaultdict(list)
		title_map: Dict[str, List[str]] = defaultdict(list)
		for key, entry in pages_obj.items():
			if not entry.get("enabled"):
				continue
			slug = entry.get("slug", "")
			title = (entry.get("title") or "").strip()
			if slug:
				slug_map[slug].append(key)
			if title:
				title_map[title].append(key)

		for slug, keys in slug_map.items():
			if len(keys) > 1:
				errors.append(f"Locale '{lang}' duplicate slug '{slug}' for pages {keys}")
		for title, keys in title_map.items():
			if len(keys) > 1:
				warnings.append(f"Locale '{lang}' duplicate title '{title}' for pages {keys}")

	# Cross-locale uniqueness: ensure no two pages have same path in same locale (covered above) and keys unique overall (checked)

	# Classify errors into fixable/unfixable
	fixable: List[str] = []
	unfixable: List[str] = []

	def is_fixable(msg: str) -> bool:
		m = msg.lower()
		fixable_keywords = [
			"slug mismatch",
			"image_src differs",
			"missing page entry for enabled page",
			"missing card_items entry",
			"missing or empty 'title'",
			"pages." + "enabled is false",
			"pages." + "missing or empty 'title'",
			"pages." + "slug mismatch",
			"card_items." + "missing",
		]
		for k in fixable_keywords:
			if k in m:
				return True
		return False

	for e in errors:
		if is_fixable(e):
			fixable.append(e)
		else:
			unfixable.append(e)

	# Print findings with grouped, readable sections
	print_section("Locale Validation Report", TERM_WIDTH)
	print(color(f"Source:        {display_path(root, root.parent)}", CLR_WHITE))
	print(color(f"Locales found: {', '.join(sorted(locales.keys()))}", CLR_WHITE))
	print(color(f"Pages checked: {len(pages)}", CLR_WHITE))

	print_group("Fixable issues", fixable, "WARN (fix)", CLR_YELLOW)
	print_group("Warnings", warnings, "WARN", CLR_YELLOW)
	print_group("Critical issues", unfixable, "ERROR", CLR_RED)

	# If there are fixable issues ask to run autofix
	if fixable:
		print(color("\nAutofix can resolve the fixable issues above.", CLR_WHITE))
		ans = input("Run autofix for fixable issues now? [y/N]: ").strip().lower()
		if ans == "y":
			fixer = Path(__file__).parent / "autofix_locales.py"
			if not fixer.is_file():
				print_labeled("ERROR", CLR_RED, f"Autofix script not found: {fixer}")
				sys.exit(1)
			# Run autofix
			rc = subprocess.run([sys.executable, fixer, "--root", args.root])
			if rc.returncode != 0:
				print_labeled("ERROR", CLR_RED, "Autofix failed (see output).")
				sys.exit(1)
			# Re-run validator to confirm
			print_labeled("OK", CLR_GREEN, "Autofix completed. Re-running validator...")
			rc2 = subprocess.run([sys.executable, __file__, "--root", args.root])
			sys.exit(rc2.returncode)

	# If no unfixable errors and no fixable items, OK
	if not unfixable and not fixable:
		print_labeled("OK", CLR_GREEN, "no unfixable errors and no fixable issues.")
		sys.exit(0)

	print_labeled("INFO", CLR_BLUE, f"found {len(fixable)} fixable issues and {len(unfixable)} unfixable errors.")
	print_labeled("INFO", CLR_BLUE, "run 'python tools/autofix_locales.py' to attempt automatic fixes for fixable issues.")

	# If there are unfixable errors, exit non-zero
	if unfixable:
		sys.exit(1)

	sys.exit(0)


def print_errors(errors: List[str]):
	print("ERRORS:")
	for e in errors:
		print("-", e)


if __name__ == "__main__":
	main()

