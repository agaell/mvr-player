"""Compatibility package for running MVR Player from the repository root."""

from pathlib import Path

__version__ = "0.1.0"

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "mvr_player"
if _SRC_PACKAGE.is_dir():
    __path__.append(str(_SRC_PACKAGE))
