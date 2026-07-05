"""Copy the private contact-form SMTP config into the built dist layout.

Production builds keep one contact.php per language root, so the config lives
next to the English endpoint at dist/en/.private. Preview builds serve language
roots under a URL prefix and share one root-level private directory, so the
config lives at dist/.private.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_YELLOW, display_path, print_labeled


CONFIG_NAME = "pca-contact-config.json"
PRIVATE_HTACCESS = "Require all denied\n"


def copy_config(src: Path, private_dir: Path) -> None:
    private_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, private_dir / CONFIG_NAME)
    (private_dir / ".htaccess").write_text(PRIVATE_HTACCESS, encoding="utf-8")


def copy_contact_config(root: Path, dist: Path, preview: bool) -> bool:
    config_src = root / CONFIG_NAME
    if not config_src.is_file():
        print_labeled(
            "WARN",
            CLR_YELLOW,
            f"contact config not found: {display_path(config_src, root)}",
        )
        return False

    if preview:
        targets = [dist / ".private"]
    else:
        targets = [dist / "en" / ".private"]

    for private_dir in targets:
        copy_config(config_src, private_dir)
        print_labeled("OK", CLR_GREEN, f"copied contact config to {display_path(private_dir, root.parent)}")

    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy PCA contact config into site-dist.")
    parser.add_argument("--root", default=".", help="site source root")
    parser.add_argument("--dist", default=None, help="built dist directory")
    parser.add_argument("--preview", action="store_true", help="use preview dist layout")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    dist = Path(args.dist).expanduser().resolve() if args.dist else root.parent / "site-dist"
    copy_contact_config(root, dist, args.preview)


if __name__ == "__main__":
    main()
