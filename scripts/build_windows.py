"""Build the Windows executable for MVR Player."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run the shared local build script on Windows."""
    if os.name != "nt":
        raise SystemExit("Windows-сборку нужно запускать в Windows.")

    command = [sys.executable, str(PROJECT_ROOT / "build.py")]
    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


if __name__ == "__main__":
    main()
