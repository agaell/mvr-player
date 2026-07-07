"""User interface primitives."""

import tkinter as tk

from .settings import APP_NAME, DEFAULT_WINDOW_SIZE


def create_main_window() -> tk.Tk:
    """Create the main application window."""
    window = tk.Tk()
    window.title(APP_NAME)
    window.geometry(DEFAULT_WINDOW_SIZE)
    return window

