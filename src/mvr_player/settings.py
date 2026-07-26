"""Application settings and persisted user preferences."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "MVR Player"
APP_VERSION = "0.1.0"
DEFAULT_WINDOW_SIZE = "960x600"
MIN_WINDOW_SIZE = (760, 480)

def _resource_root() -> Path:
    """Return the project folder or PyInstaller's unpacked resource folder."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root is not None:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _resource_root()
ASSETS_DIR = PROJECT_ROOT / "assets"
USER_DATA_DIR = Path.home() / ".mvr-player"
USER_SETTINGS_FILE = USER_DATA_DIR / "settings.json"
APP_ICON_FILES = (
    ASSETS_DIR / "icons" / "app-icon-16.png",
    ASSETS_DIR / "icons" / "app-icon-32.png",
    ASSETS_DIR / "icons" / "app-icon-48.png",
    ASSETS_DIR / "icons" / "app-icon-64.png",
    ASSETS_DIR / "icons" / "app-icon-128.png",
    ASSETS_DIR / "icons" / "app-icon-256.png",
    ASSETS_DIR / "icons" / "app-icon-512.png",
    ASSETS_DIR / "icons" / "app-icon.ico",
    ASSETS_DIR / "logo.png",
)


@dataclass
class UserSettings:
    """Small, best-effort store for preferences outside the repository."""

    settings_file: Path = field(default_factory=lambda: USER_SETTINGS_FILE)
    last_open_directory: Path | None = None
    mp4_output_directory: Path | None = None

    @classmethod
    def load(cls, settings_file: str | Path | None = None) -> "UserSettings":
        """Load saved folder choices, falling back to empty preferences."""
        path = Path(settings_file) if settings_file is not None else USER_SETTINGS_FILE
        preferences = cls(settings_file=path)

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return preferences

        if not isinstance(data, dict):
            return preferences

        preferences.last_open_directory = _existing_directory(data.get("last_open_directory"))
        preferences.mp4_output_directory = _existing_directory(data.get("mp4_output_directory"))
        return preferences

    def remember_open_directory(self, directory: str | Path) -> None:
        """Save the directory last used to open a video."""
        self.last_open_directory = _existing_directory(directory)
        self.save()

    def remember_mp4_output_directory(self, directory: str | Path) -> None:
        """Save the directory last chosen for a converted MP4."""
        self.mp4_output_directory = _existing_directory(directory)
        self.save()

    def save(self) -> bool:
        """Persist preferences atomically; failures must not affect playback."""
        data = {
            "last_open_directory": _path_text(self.last_open_directory),
            "mp4_output_directory": _path_text(self.mp4_output_directory),
        }
        temporary_file = self.settings_file.with_name(f".{self.settings_file.name}.tmp")

        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            temporary_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            temporary_file.replace(self.settings_file)
        except OSError:
            try:
                temporary_file.unlink(missing_ok=True)
            except OSError:
                pass
            return False

        return True


def _existing_directory(value: object) -> Path | None:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return None

    try:
        directory = Path(value).expanduser()
        return directory if directory.is_dir() else None
    except (OSError, ValueError):
        return None


def _path_text(path: Path | None) -> str | None:
    return str(path) if path is not None else None
