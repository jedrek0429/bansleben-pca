"""PCA builder app entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

BUILD_PACKAGE_DIR = Path(__file__).resolve().with_name("build")
if str(BUILD_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(BUILD_PACKAGE_DIR))

from runner import main


if __name__ == "__main__":
    main()
