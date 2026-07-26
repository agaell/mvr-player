"""Build a standalone MVR Player application with PyInstaller."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path


APP_NAME = "MVR Player"
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
ICON_PATH = ASSETS_DIR / "icons" / "app-icon.ico"
SOURCE_DIR = PROJECT_ROOT / "src"
ENTRY_POINT = PROJECT_ROOT / "scripts" / "pyinstaller_entry.py"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"


def build() -> Path:
    """Create the Windows executable in the project's ``dist`` directory."""
    if os.name != "nt":
        raise RuntimeError("Windows-приложение можно собрать только в Windows.")
    if find_spec("PyInstaller") is None:
        raise RuntimeError("Установите PyInstaller: python -m pip install pyinstaller")

    _require_file(ENTRY_POINT, "точку входа приложения")
    _require_file(ICON_PATH, "иконку приложения")
    if not ASSETS_DIR.is_dir():
        raise RuntimeError(f"Не найдена папка с ресурсами: {ASSETS_DIR}")

    data_separator = ";" if os.name == "nt" else ":"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        APP_NAME,
        "--icon",
        str(ICON_PATH),
        "--add-data",
        f"{ASSETS_DIR}{data_separator}assets",
        "--collect-all",
        "imageio_ffmpeg",
        "--paths",
        str(SOURCE_DIR),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR / "pyinstaller"),
        "--specpath",
        str(BUILD_DIR),
        str(ENTRY_POINT),
    ]

    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    except FileNotFoundError as exc:
        raise RuntimeError("Не удалось запустить Python для сборки.") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Сборка PyInstaller завершилась с ошибкой.") from exc

    artifact = DIST_DIR / f"{APP_NAME}.exe"
    if not artifact.is_file():
        raise RuntimeError(f"PyInstaller не создал ожидаемый файл: {artifact}")

    print(f"Готово: {artifact}")
    return artifact


def _require_file(path: Path, description: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Не удалось найти {description}: {path}")


if __name__ == "__main__":
    try:
        build()
    except RuntimeError as exc:
        raise SystemExit(f"Ошибка сборки: {exc}") from exc
