"""
Publish the editor directory to a destination directory.

Example:
    python dev_publish_editor.py --dest /path/to/public_html/en/editor
"""
import argparse
import subprocess
import shutil
from pathlib import Path

from common import CLR_GREEN, CLR_RED, CLR_BLUE, CLR_WHITE, color, display_path, print_group, print_labeled, print_section


DEFAULT_ROOT = Path(__file__).parents[2].resolve()
DEFAULT_PUBLIC_HTML = DEFAULT_ROOT / "public_html"
DEFAULT_EDITOR = DEFAULT_PUBLIC_HTML / "editor"

ROOT = DEFAULT_ROOT
PUBLIC_HTML = DEFAULT_PUBLIC_HTML
EDITOR = DEFAULT_EDITOR
DEST = None

def configure_paths(editor: Path, dest: Path) -> None:
    global EDITOR, DEST, ROOT, PUBLIC_HTML

    EDITOR = Path(editor).expanduser().resolve()
    DEST = Path(dest).expanduser().resolve()

    # Keep readable display output for the old project layout when possible.
    ROOT = DEFAULT_ROOT
    PUBLIC_HTML = DEFAULT_PUBLIC_HTML


def assert_dist_ok() -> None:
    required = [
        EDITOR / "bridge.py",
        EDITOR / "index.php",
        EDITOR / "__pycache__"
    ]

    missing = [display_path(p, ROOT) for p in required if not p.exists()]

    if missing:
        print_group("Missing build output", missing, "ERROR", CLR_RED)
        print_labeled(
            "ERROR",
            CLR_RED,
            "editor is incomplete. Compile the bridge.py first, then publish again.",
        )
        print(color("You can compile the bridge.py using python, for example:", CLR_BLUE))
        print(color("    python -m compileall public_html/editor/bridge.py", CLR_WHITE))
        raise SystemExit(1)


def publish_editor() -> str:
    if DEST is None:
        raise SystemExit("Missing required destination path.")

    DEST.mkdir(parents=True, exist_ok=True)

    if shutil.which("rsync"):
        subprocess.run(
            ["rsync", "-a", "--delete", str(EDITOR) + "/", str(DEST) + "/"],
            check=True,
        )
        return "rsync"

    if DEST.exists():
        shutil.rmtree(DEST)

    shutil.copytree(EDITOR, DEST)
    return "copytree"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish the editor directory to a destination directory."
    )
    parser.add_argument(
        "--dist",
        default=str(DEFAULT_EDITOR),
        help=f"built editor directory to publish (default: {DEFAULT_EDITOR})",
    )
    parser.add_argument(
        "--dest",
        required=True,
        help="destination directory to publish into, for example public_html/en/editor",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_paths(Path(args.dist), Path(args.dest))

    print_section("Editor Publish Report")
    print(color(f"Source:      {display_path(EDITOR, ROOT)}", CLR_WHITE))
    print(color(f"Destination: {display_path(DEST, ROOT)}", CLR_WHITE))

    assert_dist_ok()

    method = publish_editor()

    print_labeled("OK", CLR_GREEN, f"published editor using {method}.")
    print_labeled("OK", CLR_GREEN, f"destination: {display_path(DEST, ROOT)}")


if __name__ == "__main__":
    main()
