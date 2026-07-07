"""Application startup."""

from .ui import create_main_window


def run_app() -> None:
    """Start the MVR Player application."""
    app_window = create_main_window()
    app_window.run()
