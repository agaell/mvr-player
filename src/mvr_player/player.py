"""Video playback through an FFmpeg decoding process."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


@dataclass(frozen=True)
class VideoFrame:
    """Decoded RGB video frame."""

    width: int
    height: int
    data: bytes


class MvrPlayerError(Exception):
    """Base playback error."""


class PlayerFileError(MvrPlayerError):
    """Raised when the selected file cannot be used."""


class FfmpegNotFoundError(MvrPlayerError):
    """Raised when FFmpeg is not available."""


class MvrPlayer:
    """Decode video frames from an MVR file using FFmpeg."""

    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self.file_path: Path | None = None
        self.ffmpeg_path = ffmpeg_path
        self.frame_queue: queue.Queue[VideoFrame] = queue.Queue(maxsize=3)
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr_lines: deque[str] = deque(maxlen=30)
        self._last_returncode: int | None = None
        self._stop_requested = False
        self._output_size = (0, 0)

    @property
    def last_returncode(self) -> int | None:
        """Return the last finished FFmpeg return code."""
        self._refresh_process_state()
        return self._last_returncode

    @property
    def last_error(self) -> str:
        """Return recent FFmpeg stderr output."""
        return "\n".join(self._stderr_lines).strip()

    def set_file(self, file_path: str | Path) -> Path:
        """Select a file for playback."""
        path = Path(file_path).expanduser()
        if not path.exists():
            raise PlayerFileError(f"Файл не найден: {path}")
        if not path.is_file():
            raise PlayerFileError(f"Выбранный путь не является файлом: {path}")

        self.stop()
        self.file_path = path.resolve()
        self._last_returncode = None
        self._stderr_lines.clear()
        self._clear_frames()
        return self.file_path

    def preview_frame(self, max_size: tuple[int, int], timeout: float = 10) -> VideoFrame:
        """Decode one frame for immediate display after opening a file."""
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if not self.file_path.exists():
            raise PlayerFileError(f"Файл не найден: {self.file_path}")

        ffmpeg = self._find_ffmpeg()
        width, height = self._normalise_size(max_size)
        frame_size = width * height * 3
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            *self._input_args(),
            "-an",
            "-vf",
            self._video_filter(width, height),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise MvrPlayerError("FFmpeg не успел подготовить первый кадр.") from exc
        except OSError as exc:
            raise MvrPlayerError(f"Не удалось запустить FFmpeg: {exc}") from exc

        if result.returncode != 0:
            error = result.stderr.decode("utf-8", errors="replace").strip()
            raise MvrPlayerError(error or "FFmpeg не смог прочитать видео.")
        if len(result.stdout) < frame_size:
            error = result.stderr.decode("utf-8", errors="replace").strip()
            raise MvrPlayerError(error or "FFmpeg не вернул видеокадр.")

        return VideoFrame(width=width, height=height, data=result.stdout[:frame_size])

    def play(self, max_size: tuple[int, int]) -> None:
        """Start decoding the selected file into embedded UI frames."""
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if not self.file_path.exists():
            raise PlayerFileError(f"Файл не найден: {self.file_path}")
        if self.is_playing():
            return

        ffmpeg = self._find_ffmpeg()
        width, height = self._normalise_size(max_size)
        self._output_size = (width, height)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-re",
            *self._input_args(),
            "-an",
            "-vf",
            self._video_filter(width, height),
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]

        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            raise MvrPlayerError(f"Не удалось запустить FFmpeg: {exc}") from exc

        self._process = process
        self._last_returncode = None
        self._stop_requested = False
        self._stderr_lines.clear()
        self._clear_frames()

        if process.stdout is not None:
            threading.Thread(
                target=self._read_frames,
                args=(process.stdout,),
                daemon=True,
            ).start()
        if process.stderr is not None:
            threading.Thread(
                target=self._collect_stderr,
                args=(process.stderr,),
                daemon=True,
            ).start()

    def stop(self) -> None:
        """Stop playback if FFmpeg is running."""
        self._stop_requested = True
        process = self._process
        if process is None:
            return

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)

        self._last_returncode = process.returncode
        self._process = None
        self._clear_frames()

    def is_playing(self) -> bool:
        """Return whether FFmpeg is currently decoding."""
        self._refresh_process_state()
        return self._process is not None

    def read_frame(self) -> VideoFrame | None:
        """Return the newest available frame, dropping stale queued frames."""
        frame: VideoFrame | None = None
        while True:
            try:
                frame = self.frame_queue.get_nowait()
            except queue.Empty:
                return frame

    def close(self) -> None:
        """Release playback resources."""
        self.stop()

    def _normalise_size(self, max_size: tuple[int, int]) -> tuple[int, int]:
        width = max(160, int(max_size[0]))
        height = max(120, int(max_size[1]))
        return width, height

    def _video_filter(self, width: int, height: int) -> str:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "fps=24"
        )

    def _input_args(self) -> list[str]:
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if self.file_path.suffix.lower() == ".mvr":
            return ["-f", "h264", "-i", str(self.file_path)]
        return ["-i", str(self.file_path)]

    def _find_ffmpeg(self) -> str:
        if self.ffmpeg_path is not None:
            configured = Path(self.ffmpeg_path).expanduser()
            if configured.exists():
                return str(configured)

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is not None:
            return ffmpeg

        try:
            import imageio_ffmpeg
        except ImportError as exc:
            raise FfmpegNotFoundError(
                "FFmpeg не найден. Установите зависимости проекта командой "
                "pip install -e . или установите FFmpeg вручную."
            ) from exc

        try:
            bundled_ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            raise FfmpegNotFoundError(
                "Не удалось найти встроенный FFmpeg из imageio-ffmpeg."
            ) from exc

        if not Path(bundled_ffmpeg).exists():
            raise FfmpegNotFoundError(
                "Встроенный FFmpeg найден в настройках, но файл бинарника отсутствует."
            )
        return bundled_ffmpeg

    def _refresh_process_state(self) -> None:
        process = self._process
        if process is None:
            return
        returncode = process.poll()
        if returncode is not None:
            self._last_returncode = returncode
            self._process = None

    def _read_frames(self, stdout: BinaryIO) -> None:
        process = self._process
        if process is None:
            return

        width, height = self._output_size
        frame_size = width * height * 3
        with stdout:
            while not self._stop_requested:
                pixels = stdout.read(frame_size)
                if len(pixels) != frame_size:
                    break
                self._put_frame(VideoFrame(width=width, height=height, data=pixels))

    def _put_frame(self, frame: VideoFrame) -> None:
        try:
            self.frame_queue.put_nowait(frame)
            return
        except queue.Full:
            pass

        try:
            self.frame_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            self.frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    def _collect_stderr(self, stderr: BinaryIO) -> None:
        with stderr:
            for line in stderr:
                decoded_line = line.decode("utf-8", errors="replace").strip()
                if decoded_line:
                    self._stderr_lines.append(decoded_line)

    def _clear_frames(self) -> None:
        while True:
            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                break
