"""Shared FFmpeg integration helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

MVR_SOURCE_FPS = 14


class FfmpegLookupError(Exception):
    """Raised when FFmpeg cannot be located."""


def find_ffmpeg(configured_path: str | None = None) -> str:
    """Return a usable FFmpeg executable path."""
    if configured_path is not None:
        configured = Path(configured_path).expanduser()
        if configured.exists():
            return str(configured)

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is not None:
        return ffmpeg

    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise FfmpegLookupError(
            "FFmpeg не найден. Установите зависимости проекта командой "
            "pip install -e . или установите FFmpeg вручную."
        ) from exc

    try:
        bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise FfmpegLookupError("Не удалось найти встроенный FFmpeg из imageio-ffmpeg.") from exc

    if not Path(bundled_ffmpeg).exists():
        raise FfmpegLookupError(
            "Встроенный FFmpeg найден в настройках, но файл бинарника отсутствует."
        )
    return bundled_ffmpeg


def input_args_for_file(file_path: str | Path) -> list[str]:
    """Build FFmpeg input arguments for known source formats."""
    path = Path(file_path)
    if path.suffix.lower() == ".mvr":
        return ["-f", "h264", "-i", str(path)]
    return ["-i", str(path)]
