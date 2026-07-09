"""Error reporting helpers for MVR Player."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

LOG_DIR = Path.home() / ".mvr-player"
LOG_FILE = LOG_DIR / "mvr-player.log"

_LOGGER_NAME = "mvr_player"
_LOGGING_CONFIGURED = False


class UserFacingError(Exception):
    """Exception with a safe message for dialogs and optional details."""

    def __init__(self, message: str, details: str | None = None) -> None:
        super().__init__(message)
        self.details = details


def configure_error_logging() -> Path | None:
    """Configure application logging and return the active log file path."""
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return LOG_FILE

    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    except OSError:
        logging.basicConfig(
            stream=sys.stderr,
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        _LOGGING_CONFIGURED = True
        return None

    _LOGGING_CONFIGURED = True
    return LOG_FILE


def logger() -> logging.Logger:
    """Return the application logger."""
    configure_error_logging()
    return logging.getLogger(_LOGGER_NAME)


def log_exception(context: str, exc: BaseException) -> None:
    """Write an exception with traceback to the application log."""
    logger().error("%s: %s", context, exc, exc_info=(type(exc), exc, exc.__traceback__))


def traceback_text(exc: BaseException) -> str:
    """Return a formatted traceback for dialog details."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def user_message(exc: object, fallback: str = "Произошла ошибка.") -> str:
    """Convert a technical exception into a concise Russian user message."""
    if isinstance(exc, UserFacingError):
        return str(exc) or fallback

    text = str(exc).strip() if exc is not None else ""
    if not text:
        return fallback

    lowered = text.lower()
    if "permission denied" in lowered or "operation not permitted" in lowered:
        return "Нет прав доступа к файлу или папке. Проверьте разрешения и попробуйте снова."
    if "no such file or directory" in lowered:
        return "Файл или папка не найдены. Проверьте путь и попробуйте снова."
    if "invalid data found" in lowered or "could not find codec parameters" in lowered:
        return "FFmpeg не смог распознать видео. Возможно, файл повреждён или имеет другой формат."
    if "moov atom not found" in lowered:
        return "Видео выглядит повреждённым: MP4-структура не найдена."
    if "unknown decoder" in lowered or "decoder not found" in lowered:
        return "В установленном FFmpeg нет нужного декодера для этого файла."
    if "encoder" in lowered and "not found" in lowered:
        return "В установленном FFmpeg нет нужного кодека для сохранения MP4."
    if "ffmpeg" in lowered and "not found" in lowered:
        return "FFmpeg не найден. Установите зависимости проекта или FFmpeg вручную."

    return text
