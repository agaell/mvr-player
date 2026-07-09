"""Application settings."""

from pathlib import Path

APP_NAME = "MVR Player"
APP_VERSION = "0.1.0"
DEFAULT_WINDOW_SIZE = "960x600"
MIN_WINDOW_SIZE = (760, 480)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
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
