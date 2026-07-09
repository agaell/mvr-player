"""Application startup."""

from __future__ import annotations

from pathlib import Path

from .errors import configure_error_logging, logger
from .settings import APP_VERSION
from .ui import UI_BUILD, create_main_window


def run_app(initial_file: str | Path | None = None) -> None:
    """Start the MVR Player application."""
    configure_error_logging()
    logger().info("Starting MVR Player %s (%s)", APP_VERSION, UI_BUILD)
    print(f"Starting MVR Player {APP_VERSION} ({UI_BUILD}) from {__file__}", flush=True)
    app_window = create_main_window(initial_file=initial_file)
    app_window.run()
