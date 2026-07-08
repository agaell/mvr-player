"""Repository-root entry point for MVR Player."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _maybe_reexec_local_venv() -> None:
    """Use the project virtualenv when the repo is launched with system Python."""
    if os.environ.get("MVR_PLAYER_VENV_REEXEC") == "1":
        return

    project_root = Path(__file__).resolve().parent.parent
    candidates = (
        project_root / ".venv" / "bin" / "python",
        project_root / ".venv" / "Scripts" / "python.exe",
    )
    current_python = Path(sys.executable).absolute()
    for candidate in candidates:
        if candidate.exists() and candidate.absolute() != current_python:
            env = os.environ.copy()
            env["MVR_PLAYER_VENV_REEXEC"] = "1"
            os.execve(str(candidate), [str(candidate), "-m", "mvr_player.main", *sys.argv[1:]], env)


def _print_debug_paths() -> None:
    import mvr_player
    from mvr_player import app, ui

    print(f"python: {sys.executable}")
    print(f"package: {mvr_player.__file__}")
    print(f"package_path: {list(mvr_player.__path__)}")
    print(f"app: {app.__file__}")
    print(f"ui: {ui.__file__}")
    print(f"ui_build: {ui.UI_BUILD}")


def main() -> None:
    """Run the application."""
    _maybe_reexec_local_venv()

    if "--debug-paths" in sys.argv:
        _print_debug_paths()
        return

    from .app import run_app

    initial_file = next((arg for arg in sys.argv[1:] if not arg.startswith("-")), None)
    run_app(initial_file=initial_file)


if __name__ == "__main__":
    main()
