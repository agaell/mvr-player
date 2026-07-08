"""Qt user interface for MVR Player."""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .player import FfmpegNotFoundError, MvrPlayer, MvrPlayerError, PlayerFileError, VideoFrame
from .settings import APP_NAME, APP_VERSION, DEFAULT_WINDOW_SIZE, MIN_WINDOW_SIZE

UI_BUILD = f"qt-playback-{APP_VERSION}"


class QtMvrPlayerApp:
    """Small wrapper that owns the QApplication instance."""

    def __init__(self, initial_file: str | Path | None = None) -> None:
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setApplicationName(APP_NAME)
        self.app.setApplicationVersion(APP_VERSION)

        self.window = MvrPlayerMainWindow()
        if initial_file is not None:
            QTimer.singleShot(250, lambda: self.window.open_file(initial_file))

    def run(self) -> None:
        """Show the main window and start the Qt event loop."""
        self.window.show()
        self.app.exec()


class MvrPlayerMainWindow(QMainWindow):
    """Main Qt window with embedded frame playback."""

    def __init__(self) -> None:
        super().__init__()
        self.player = MvrPlayer()
        self.selected_file: Path | None = None
        self._load_generation = 0
        self._load_events: queue.Queue[tuple[str, int, object]] = queue.Queue()
        self._preview_image: QImage | None = None
        self._last_pixmap: QPixmap | None = None
        self._first_frame_seen = False
        self._playback_started = False
        self._closing = False

        self.load_timer = QTimer(self)
        self.load_timer.setInterval(40)
        self.load_timer.timeout.connect(self._pump_load_events)
        self.load_timer.start()

        self.frame_timer = QTimer(self)
        self.frame_timer.setInterval(24)
        self.frame_timer.timeout.connect(self._poll_player)

        self._configure_window()
        self._create_actions()
        self._create_menu()
        self._create_layout()
        self._apply_styles()
        self._show_empty_state()

    def _configure_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        width, height = _parse_geometry(DEFAULT_WINDOW_SIZE, fallback=(960, 600))
        self.resize(width, height)
        self.setMinimumSize(QSize(*MIN_WINDOW_SIZE))
        self.setAcceptDrops(True)

    def _create_actions(self) -> None:
        self.open_action = QAction("Открыть MVR...", self)
        self.open_action.triggered.connect(self.open_dialog)

        self.exit_action = QAction("Выход", self)
        self.exit_action.triggered.connect(self.close)

        self.reset_view_action = QAction("Сбросить вид", self)
        self.reset_view_action.triggered.connect(self._reset_view)

        self.about_action = QAction("О программе", self)
        self.about_action.triggered.connect(self._show_about)

    def _create_menu(self) -> None:
        menu_bar = QMenuBar(self)

        file_menu = menu_bar.addMenu("Файл")
        file_menu.addAction(self.open_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        view_menu = menu_bar.addMenu("Вид")
        view_menu.addAction(self.reset_view_action)

        help_menu = menu_bar.addMenu("Справка")
        help_menu.addAction(self.about_action)

        self.setMenuBar(menu_bar)

    def _create_layout(self) -> None:
        root = QWidget(self)
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 16, 18, 0)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        header = QFrame(root)
        header.setObjectName("Header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 18, 14)
        header_layout.setSpacing(10)

        title_box = QWidget(header)
        title_layout = QVBoxLayout(title_box)
        title_layout.setContentsMargins(0, 0, 14, 0)
        title_layout.setSpacing(2)

        self.title_label = QLabel(APP_NAME, title_box)
        self.title_label.setObjectName("TitleLabel")
        self.version_label = QLabel(f"Интерфейс {APP_VERSION}", title_box)
        self.version_label.setObjectName("VersionLabel")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.version_label)

        self.open_button = QPushButton("Открыть MVR", header)
        self.open_button.setObjectName("PrimaryButton")
        self.open_button.clicked.connect(self.open_dialog)

        self.convert_button = QPushButton("Конвертировать в MP4", header)
        self.convert_button.setObjectName("SecondaryButton")
        self.convert_button.setEnabled(False)
        self.convert_button.clicked.connect(self._convert_to_mp4)

        self.play_button = QPushButton("Play", header)
        self.play_button.setObjectName("SecondaryButton")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play)

        self.stop_button = QPushButton("Pause / Stop", header)
        self.stop_button.setObjectName("SecondaryButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_playback)

        self.file_label = QLabel("Файл не выбран", header)
        self.file_label.setObjectName("FileLabel")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.file_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        header_layout.addWidget(title_box)
        header_layout.addWidget(self.open_button)
        header_layout.addWidget(self.convert_button)
        header_layout.addWidget(self.play_button)
        header_layout.addWidget(self.stop_button)
        header_layout.addWidget(self.file_label, 1)
        root_layout.addWidget(header)

        self.video_shell = QFrame(root)
        self.video_shell.setObjectName("VideoShell")
        self.video_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        video_layout = QStackedLayout(self.video_shell)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self.video_stack = video_layout

        self.empty_view = QWidget(self.video_shell)
        self.empty_view.setObjectName("EmptyView")
        empty_layout = QVBoxLayout(self.empty_view)
        empty_layout.setContentsMargins(28, 28, 28, 28)
        empty_layout.setSpacing(12)
        empty_layout.addStretch(1)

        self.empty_title = QLabel("Перетащите или откройте файл", self.empty_view)
        self.empty_title.setObjectName("EmptyTitle")
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setWordWrap(True)

        self.empty_hint = QLabel("Поддерживаются MVR-файлы. Также можно выбрать любой файл через меню.", self.empty_view)
        self.empty_hint.setObjectName("EmptyHint")
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setWordWrap(True)

        self.empty_button = QPushButton("Открыть файл", self.empty_view)
        self.empty_button.setObjectName("LargeOpenButton")
        self.empty_button.clicked.connect(self.open_dialog)

        empty_layout.addWidget(self.empty_title)
        empty_layout.addWidget(self.empty_hint)
        empty_layout.addSpacing(8)
        empty_layout.addWidget(self.empty_button, alignment=Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch(1)

        self.video_label = QLabel(self.video_shell)
        self.video_label.setObjectName("VideoLabel")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setMinimumSize(320, 220)
        self.video_label.setScaledContents(False)

        self.video_stack.addWidget(self.empty_view)
        self.video_stack.addWidget(self.video_label)
        root_layout.addWidget(self.video_shell, 1)
        self._install_drop_handlers(root)

        status_bar = QStatusBar(self)
        status_bar.setObjectName("StatusBar")
        self.setStatusBar(status_bar)
        self.statusBar().showMessage(f"Готово - {UI_BUILD}")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#Root {
                background: #f4f7fb;
                color: #111827;
                font-size: 13px;
            }
            QMenuBar {
                background: #ffffff;
                color: #111827;
                padding: 4px;
            }
            QMenuBar::item:selected,
            QMenu::item:selected {
                background: #e8eef8;
            }
            QMenu {
                background: #ffffff;
                border: 1px solid #d7dde8;
                padding: 4px;
            }
            QFrame#Header {
                background: #ffffff;
                border: 1px solid #dce3ee;
                border-radius: 8px;
            }
            QLabel#TitleLabel {
                font-size: 18px;
                font-weight: 700;
                color: #0f172a;
            }
            QLabel#VersionLabel,
            QLabel#FileLabel {
                color: #64748b;
            }
            QPushButton {
                min-height: 34px;
                padding: 0 14px;
                border-radius: 7px;
                border: 1px solid #cbd5e1;
                background: #ffffff;
                color: #0f172a;
                font-weight: 600;
            }
            QPushButton:hover:!disabled {
                background: #f8fafc;
                border-color: #94a3b8;
            }
            QPushButton:pressed:!disabled {
                background: #e2e8f0;
            }
            QPushButton:disabled {
                background: #eef2f7;
                color: #94a3b8;
                border-color: #d8e0eb;
            }
            QPushButton#PrimaryButton,
            QPushButton#LargeOpenButton {
                background: #2563eb;
                color: #ffffff;
                border-color: #2563eb;
            }
            QPushButton#PrimaryButton:hover,
            QPushButton#LargeOpenButton:hover {
                background: #1d4ed8;
                border-color: #1d4ed8;
            }
            QPushButton#LargeOpenButton {
                min-height: 44px;
                min-width: 170px;
                font-size: 15px;
            }
            QFrame#VideoShell {
                background: #05070b;
                border: 1px solid #111827;
                border-radius: 8px;
            }
            QWidget#EmptyView {
                background: #05070b;
                border-radius: 8px;
            }
            QLabel#EmptyTitle {
                color: #f8fafc;
                font-size: 28px;
                font-weight: 700;
            }
            QLabel#EmptyHint {
                color: #a9b4c3;
                font-size: 14px;
            }
            QLabel#VideoLabel {
                background: #000000;
                border-radius: 8px;
            }
            QStatusBar#StatusBar {
                background: #edf2f8;
                color: #334155;
            }
            """
        )

    def open_dialog(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть MVR",
            str(Path.home()),
            "MVR-файлы (*.mvr);;Все файлы (*)",
        )
        if filename:
            self.open_file(filename)

    def open_file(self, file_path: str | Path) -> None:
        path = Path(file_path).expanduser()
        self._load_generation += 1
        generation = self._load_generation

        self.frame_timer.stop()
        self._playback_started = False
        self._first_frame_seen = False
        self.selected_file = None
        self.player.stop()
        self._set_file_controls_enabled(False)
        self._last_pixmap = None
        self._preview_image = None

        self.file_label.setText(path.name)
        self._show_empty_state(
            "Загрузка видео...",
            f"{path.name}\nГотовлю первый кадр через FFmpeg",
            "Открыть другой файл",
        )
        self.statusBar().showMessage(f"Файл выбран: {path}")
        QApplication.processEvents()

        size = self._video_surface_size()
        threading.Thread(
            target=self._load_preview_worker,
            args=(generation, path, size),
            daemon=True,
        ).start()

    def _load_preview_worker(self, generation: int, path: Path, size: tuple[int, int]) -> None:
        preview_player = MvrPlayer()
        try:
            resolved_path = preview_player.set_file(path)
            preview = preview_player.preview_frame(size)
        except (PlayerFileError, MvrPlayerError) as exc:
            self._load_events.put(("error", generation, exc))
            return

        self._load_events.put(("ready", generation, (resolved_path, preview)))

    def _pump_load_events(self) -> None:
        while True:
            try:
                event_name, generation, payload = self._load_events.get_nowait()
            except queue.Empty:
                break

            if generation != self._load_generation or self._closing:
                continue
            if event_name == "ready":
                path, preview = payload
                self._on_preview_ready(generation, path, preview)
            elif event_name == "error":
                self._on_preview_error(payload)

    def _on_preview_ready(self, generation: int, path: Path, preview: VideoFrame) -> None:
        try:
            self.player.set_file(path)
        except (PlayerFileError, MvrPlayerError) as exc:
            self._on_preview_error(exc)
            return

        self.selected_file = path
        self._set_file_controls_enabled(True)
        self.file_label.setText(path.name)
        self.statusBar().showMessage("Первый кадр показан. Запускаю воспроизведение...")
        self._display_frame(preview)
        QTimer.singleShot(120, lambda: self.play() if generation == self._load_generation else None)

    def _on_preview_error(self, exc: object) -> None:
        self.selected_file = None
        self.player.stop()
        self._set_file_controls_enabled(False)
        self.file_label.setText("Файл не выбран")
        self._show_empty_state(
            "Видео не прочитано",
            str(exc) or "Не удалось получить первый кадр",
            "Открыть другой файл",
        )
        self.statusBar().showMessage("Не удалось получить первый кадр")
        QMessageBox.critical(self, "Не удалось открыть видео", str(exc))

    def play(self) -> None:
        if self.selected_file is None:
            self.statusBar().showMessage("Сначала выберите MVR-файл")
            return
        if self.player.is_playing():
            return

        self._first_frame_seen = self._last_pixmap is not None
        try:
            self.player.play(max_size=self._video_surface_size())
        except FfmpegNotFoundError as exc:
            self._handle_play_error("FFmpeg не найден", str(exc))
            return
        except MvrPlayerError as exc:
            self._handle_play_error("Ошибка воспроизведения", str(exc))
            return

        self._playback_started = True
        self._set_playback_controls(True)
        self.statusBar().showMessage(f"Воспроизведение: {self.selected_file}")
        self.frame_timer.start()

    def stop_playback(self) -> None:
        self.frame_timer.stop()
        self.player.stop()
        self._playback_started = False
        self._set_playback_controls(False)
        if self.selected_file is None:
            self._show_empty_state()
            self.statusBar().showMessage("Файл не выбран")
            return

        self.statusBar().showMessage(f"Воспроизведение остановлено: {self.selected_file}")

    def _poll_player(self) -> None:
        frame = self.player.read_frame()
        if frame is not None:
            self._first_frame_seen = True
            self._display_frame(frame)

        if self.player.is_playing():
            return

        self.frame_timer.stop()
        if not self._playback_started:
            return

        self._playback_started = False
        self._set_playback_controls(False)
        if self.player.last_returncode in (None, 0) or self._closing:
            self.statusBar().showMessage("Воспроизведение завершено")
            return

        details = self.player.last_error
        message = "FFmpeg завершился с ошибкой."
        if details:
            message = f"{message}\n\n{details}"
        self._show_empty_state("Не удалось воспроизвести файл", "Проверьте формат файла и FFmpeg", "Открыть другой файл")
        self.statusBar().showMessage("Воспроизведение завершилось с ошибкой")
        QMessageBox.critical(self, "Ошибка воспроизведения", message)

    def _display_frame(self, frame: VideoFrame) -> None:
        image = QImage(
            frame.data,
            frame.width,
            frame.height,
            frame.width * 3,
            QImage.Format.Format_RGB888,
        ).copy()
        self._preview_image = image
        self._last_pixmap = QPixmap.fromImage(image)
        self._render_current_pixmap()
        self.video_stack.setCurrentWidget(self.video_label)

    def _render_current_pixmap(self) -> None:
        if self._last_pixmap is None:
            return

        target_size = self.video_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            self.video_label.setPixmap(self._last_pixmap)
            return

        pixmap = self._last_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

    def _show_empty_state(
        self,
        title: str = "Перетащите или откройте файл",
        hint: str = "Поддерживаются MVR-файлы. Также можно выбрать любой файл через меню.",
        button_text: str = "Открыть файл",
    ) -> None:
        self.empty_title.setText(title)
        self.empty_hint.setText(hint)
        self.empty_button.setText(button_text)
        self.video_label.clear()
        self.video_stack.setCurrentWidget(self.empty_view)

    def _set_file_controls_enabled(self, enabled: bool) -> None:
        self.convert_button.setEnabled(enabled)
        self.play_button.setEnabled(enabled)
        self.stop_button.setEnabled(False)

    def _set_playback_controls(self, is_playing: bool) -> None:
        self.play_button.setEnabled(not is_playing and self.selected_file is not None)
        self.stop_button.setEnabled(is_playing)
        self.convert_button.setEnabled(self.selected_file is not None)

    def _handle_play_error(self, title: str, message: str) -> None:
        self._set_playback_controls(False)
        self.statusBar().showMessage(title)
        self._show_empty_state("Видео не запущено", message, "Открыть другой файл")
        QMessageBox.critical(self, "Не удалось воспроизвести файл", message)

    def _convert_to_mp4(self) -> None:
        if self.selected_file is None:
            self.statusBar().showMessage("Сначала выберите MVR-файл")
            return

        self.statusBar().showMessage("Конвертация пока не реализована")
        QMessageBox.information(self, "Конвертация", "Конвертация в MP4 пока не реализована.")

    def _reset_view(self) -> None:
        if self._last_pixmap is not None:
            self._render_current_pixmap()
            self.video_stack.setCurrentWidget(self.video_label)
        else:
            self._show_empty_state()
        self.statusBar().showMessage("Вид сброшен")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            f"О программе {APP_NAME}",
            (
                f"{APP_NAME}\n\n"
                f"Версия: {APP_VERSION}\n"
                f"Интерфейс: {UI_BUILD}\n\n"
                "Приложение для просмотра .mvr файлов и будущей конвертации в .mp4."
            ),
        )

    def _video_surface_size(self) -> tuple[int, int]:
        size = self.video_label.size()
        width = max(320, size.width())
        height = max(220, size.height())
        return width, height

    def _install_drop_handlers(self, root: QWidget) -> None:
        for widget in (root, self.video_shell, self.empty_view, self.video_label):
            widget.setAcceptDrops(True)
            widget.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.DragEnter and event.mimeData().hasUrls():
            event.acceptProposedAction()
            return True
        if event.type() == QEvent.Type.Drop:
            return self._handle_drop_event(event)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render_current_pixmap()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        self._handle_drop_event(event)

    def _handle_drop_event(self, event) -> bool:
        urls = event.mimeData().urls()
        for url in urls:
            if url.isLocalFile():
                self.open_file(url.toLocalFile())
                event.acceptProposedAction()
                return True
        event.ignore()
        return True

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self._closing = True
        self.load_timer.stop()
        self.frame_timer.stop()
        self.player.close()
        event.accept()


def _parse_geometry(value: str, fallback: tuple[int, int]) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", maxsplit=1)
        return int(width_text), int(height_text)
    except (AttributeError, TypeError, ValueError):
        return fallback


def create_main_window(initial_file: str | Path | None = None) -> QtMvrPlayerApp:
    """Create the main application window object."""
    return QtMvrPlayerApp(initial_file=initial_file)
