"""Compatibility entry point for the shared build/publish pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).resolve().with_name("build_and_publish.py")


if __name__ == "__main__":
    completed = subprocess.run([sys.executable, str(SCRIPT), *sys.argv[1:]])
    raise SystemExit(completed.returncode)
