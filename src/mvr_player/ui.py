"""Tkinter user interface for MVR Player."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .settings import APP_NAME, DEFAULT_WINDOW_SIZE, MIN_WINDOW_SIZE


class MvrPlayerWindow:
    """Main application window."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.status_var = tk.StringVar(value="Готово")
        self.selected_file: Path | None = None

        self._configure_window()
        self._configure_styles()
        self._create_menu()
        self._create_layout()

    def run(self) -> None:
        """Start the Tkinter event loop."""
        self.root.mainloop()

    def _configure_window(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry(DEFAULT_WINDOW_SIZE)
        self.root.minsize(*MIN_WINDOW_SIZE)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self.root.configure(bg="#f5f7fb")
        style.configure("App.TFrame", background="#f5f7fb")
        style.configure("Toolbar.TFrame", background="#ffffff")
        style.configure("Video.TFrame", background="#111827")
        style.configure("Status.TLabel", background="#eef2f7", foreground="#374151")
        style.configure("Title.TLabel", background="#111827", foreground="#e5e7eb")
        style.configure("Muted.TLabel", background="#111827", foreground="#9ca3af")
        style.configure("Primary.TButton", padding=(18, 12), font=("TkDefaultFont", 12, "bold"))
        style.configure("Secondary.TButton", padding=(18, 12), font=("TkDefaultFont", 12))

    def _create_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Открыть MVR...", command=self._open_mvr)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self._on_close)
        menu_bar.add_cascade(label="Файл", menu=file_menu)

        view_menu = tk.Menu(menu_bar, tearoff=False)
        view_menu.add_command(label="Сбросить вид", command=self._reset_view)
        menu_bar.add_cascade(label="Вид", menu=view_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="О программе", command=self._show_about)
        menu_bar.add_cascade(label="Справка", menu=help_menu)

        self.root.config(menu=menu_bar)

    def _create_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, style="Toolbar.TFrame", padding=(20, 16))
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(2, weight=1)

        open_button = ttk.Button(
            toolbar,
            text="Открыть MVR",
            style="Primary.TButton",
            command=self._open_mvr,
        )
        open_button.grid(row=0, column=0, sticky="w")

        convert_button = ttk.Button(
            toolbar,
            text="Конвертировать в MP4",
            style="Secondary.TButton",
            state=tk.DISABLED,
        )
        convert_button.grid(row=0, column=1, padx=(12, 0), sticky="w")

        video_area = ttk.Frame(self.root, style="Video.TFrame", padding=24)
        video_area.grid(row=1, column=0, sticky="nsew", padx=20, pady=(18, 20))
        video_area.columnconfigure(0, weight=1)
        video_area.rowconfigure(0, weight=1)

        placeholder = ttk.Frame(video_area, style="Video.TFrame")
        placeholder.grid(row=0, column=0)

        title_label = ttk.Label(
            placeholder,
            text="Область видео",
            style="Title.TLabel",
            font=("TkDefaultFont", 18, "bold"),
        )
        title_label.grid(row=0, column=0, pady=(0, 8))

        hint_label = ttk.Label(
            placeholder,
            text="Здесь будет отображаться содержимое MVR-файла",
            style="Muted.TLabel",
            font=("TkDefaultFont", 11),
        )
        hint_label.grid(row=1, column=0)

        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor="w",
            padding=(14, 6),
        )
        status_bar.grid(row=2, column=0, sticky="ew")

    def _open_mvr(self) -> None:
        filename = filedialog.askopenfilename(
            title="Открыть MVR",
            filetypes=(("MVR files", "*.mvr"), ("All files", "*.*")),
        )
        if not filename:
            self.status_var.set("Открытие файла отменено")
            return

        self.selected_file = Path(filename)
        self.status_var.set(f"Выбран файл: {self.selected_file.name}")

    def _reset_view(self) -> None:
        self.status_var.set("Вид сброшен")

    def _show_about(self) -> None:
        messagebox.showinfo(
            title=f"О программе {APP_NAME}",
            message=(
                "MVR Player\n\n"
                "Приложение для просмотра .mvr файлов и конвертации в .mp4.\n"
                "Воспроизведение и конвертация пока не реализованы."
            ),
        )

    def _on_close(self) -> None:
        self.root.destroy()


def create_main_window() -> MvrPlayerWindow:
    """Create the main application window object."""
    return MvrPlayerWindow()
