"""Shared helpers for site-src tool scripts."""

from __future__ import annotations

from pathlib import Path
import json
import shutil
import textwrap


CLR_RED = "\x1b[31m"
CLR_YELLOW = "\x1b[33m"
CLR_GREEN = "\x1b[32m"
CLR_BLUE = "\x1b[34m"
CLR_WHITE = "\x1b[37m"
CLR_RESET = "\x1b[0m"
DEFAULT_TERM_WIDTH = min(shutil.get_terminal_size((120, 20)).columns, 140)


def color(text: str, c: str) -> str:
	return f"{c}{text}{CLR_RESET}"


def wrap_text(text: str, width: int) -> list[str]:
	return textwrap.wrap(
		text,
		width=width,
		break_long_words=False,
		break_on_hyphens=False,
	) or [""]


def print_labeled(
	label: str,
	label_color: str,
	message: str,
	indent: int = 0,
	number: int | None = None,
	width: int = 100,
) -> None:
	label_text = f"{label} {number:>3}." if number is not None else label
	prefix = " " * indent + color(label_text, label_color) + " "
	wrapped = textwrap.wrap(
		message,
		width=width,
		initial_indent=prefix,
		subsequent_indent=" " * len(label_text) + " " * (indent + 1),
		break_long_words=False,
		break_on_hyphens=False,
	)

	if wrapped:
		print("\n".join(wrapped))
	else:
		print(prefix.rstrip())


def print_section(title: str, term_width: int = DEFAULT_TERM_WIDTH) -> None:
	line = "=" * min(term_width, 64)
	print(color(f"\n{line}", CLR_WHITE))
	print(color(title, CLR_WHITE))
	print(color(line, CLR_WHITE))


def print_group(
	title: str,
	items: list[str],
	label: str,
	label_color: str,
	indent: int = 2,
) -> None:
	if not items:
		return

	print(color(f"\n{title} ({len(items)})", CLR_WHITE))

	for idx, msg in enumerate(items, start=1):
		print_labeled(label, label_color, f"{idx}. {msg}", indent=indent)


def load_json(path: Path):
	return json.loads(Path(path).read_text(encoding="utf-8"))


def load_optional_json(path: Path):
	path = Path(path)
	if not path.exists():
		return {}
	try:
		return load_json(path)
	except Exception:
		return {}


def display_path(path: Path, root: Path) -> str:
	path = Path(path)
	root = Path(root)
	try:
		return str(path.resolve().relative_to(root.resolve()))
	except ValueError:
		return str(path.resolve())