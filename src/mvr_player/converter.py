"""MVR to MP4 conversion through FFmpeg."""

from __future__ import annotations

import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .ffmpeg_utils import FfmpegLookupError, find_ffmpeg, input_args_for_file

CONVERSION_FPS = 24


@dataclass(frozen=True)
class ConversionProgress:
    """Current FFmpeg conversion progress."""

    frame: int = 0
    fps: float = 0.0
    out_time_seconds: float = 0.0
    speed: str = ""
    finished: bool = False


class MvrConversionError(Exception):
    """Base conversion error."""


class ConversionFileError(MvrConversionError):
    """Raised when conversion paths are invalid."""


class MvrConverter:
    """Convert MVR files to MP4 using FFmpeg."""

    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self.ffmpeg_path = ffmpeg_path
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def convert(
        self,
        source_path: str | Path,
        output_path: str | Path,
        progress_callback: Callable[[ConversionProgress], None] | None = None,
    ) -> Path:
        """Convert a selected MVR file to MP4 and return the saved path."""
        source = self._validate_source(source_path)
        output = self._normalise_output_path(output_path)
        if source == output:
            raise ConversionFileError("Нельзя сохранить MP4 поверх исходного файла.")

        try:
            ffmpeg = find_ffmpeg(self.ffmpeg_path)
        except FfmpegLookupError as exc:
            raise MvrConversionError(str(exc)) from exc

        temp_output = self._temporary_output_path(output)
        command = self._conversion_command(ffmpeg, source, temp_output)
        returncode, stderr = self._run_ffmpeg(command, progress_callback)
        if returncode != 0:
            self._remove_file_if_exists(temp_output)
            raise MvrConversionError(stderr or "FFmpeg не смог сконвертировать файл.")
        if not temp_output.exists() or temp_output.stat().st_size == 0:
            self._remove_file_if_exists(temp_output)
            raise MvrConversionError("FFmpeg завершился, но MP4-файл не был создан.")

        temp_output.replace(output)
        if progress_callback is not None:
            progress_callback(ConversionProgress(finished=True))
        return output.resolve()

    def cancel(self) -> None:
        """Terminate a running conversion process."""
        with self._lock:
            process = self._process

        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    def _conversion_command(self, ffmpeg: str, source: Path, output: Path) -> list[str]:
        input_args = input_args_for_file(source)
        if source.suffix.lower() == ".mvr":
            input_args = ["-r", str(CONVERSION_FPS), *input_args]

        return [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-y",
            "-fflags",
            "+genpts+discardcorrupt",
            *input_args,
            "-an",
            "-vf",
            f"fps={CONVERSION_FPS},setpts=N/({CONVERSION_FPS}*TB),format=yuv420p",
            "-fps_mode",
            "cfr",
            "-r",
            str(CONVERSION_FPS),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-movflags",
            "+faststart",
            "-video_track_timescale",
            str(CONVERSION_FPS * 1000),
            "-progress",
            "pipe:1",
            str(output),
        ]

    def _run_ffmpeg(
        self,
        command: list[str],
        progress_callback: Callable[[ConversionProgress], None] | None,
    ) -> tuple[int, str]:
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise MvrConversionError(f"Не удалось запустить FFmpeg: {exc}") from exc

        with self._lock:
            self._process = process

        stderr_lines: deque[str] = deque(maxlen=60)
        if process.stderr is not None:
            threading.Thread(
                target=self._collect_stderr,
                args=(process.stderr, stderr_lines),
                daemon=True,
            ).start()

        try:
            if process.stdout is not None:
                self._read_progress(process.stdout, progress_callback)
            returncode = process.wait()
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None

        return returncode, "\n".join(stderr_lines).strip()

    def _read_progress(self, stdout, progress_callback: Callable[[ConversionProgress], None] | None) -> None:
        values: dict[str, str] = {}
        for raw_line in stdout:
            line = raw_line.strip()
            if not line or "=" not in line:
                continue

            key, value = line.split("=", maxsplit=1)
            values[key] = value
            if key == "progress" and progress_callback is not None:
                progress_callback(self._progress_from_values(values))
                values = {}

    def _progress_from_values(self, values: dict[str, str]) -> ConversionProgress:
        return ConversionProgress(
            frame=_safe_int(values.get("frame")),
            fps=_safe_float(values.get("fps")),
            out_time_seconds=_parse_progress_time(values),
            speed=values.get("speed", ""),
            finished=values.get("progress") == "end",
        )

    def _collect_stderr(self, stderr, lines: deque[str]) -> None:
        with stderr:
            for line in stderr:
                decoded = line.strip()
                if decoded:
                    lines.append(decoded)

    def _validate_source(self, source_path: str | Path) -> Path:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise ConversionFileError(f"Файл не найден: {source}")
        if not source.is_file():
            raise ConversionFileError(f"Выбранный путь не является файлом: {source}")
        return source

    def _normalise_output_path(self, output_path: str | Path) -> Path:
        output = Path(output_path).expanduser()
        if output.suffix.lower() != ".mp4":
            output = output.with_suffix(".mp4")
        if not output.parent.exists():
            raise ConversionFileError(f"Папка для сохранения не найдена: {output.parent}")
        if not output.parent.is_dir():
            raise ConversionFileError(f"Путь сохранения не является папкой: {output.parent}")
        return output.resolve()

    def _temporary_output_path(self, output: Path) -> Path:
        return output.with_name(f".{output.stem}.mvr-player-tmp{output.suffix}")

    def _remove_file_if_exists(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _safe_int(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


def _safe_float(value: str | None) -> float:
    if not value or value == "N/A":
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _parse_progress_time(values: dict[str, str]) -> float:
    for key in ("out_time_us", "out_time_ms"):
        value = values.get(key)
        if value and value != "N/A":
            try:
                return int(value) / 1_000_000
            except ValueError:
                pass

    value = values.get("out_time")
    if not value or value == "N/A":
        return 0.0

    try:
        hours_text, minutes_text, seconds_text = value.split(":")
        return int(hours_text) * 3600 + int(minutes_text) * 60 + float(seconds_text)
    except ValueError:
        return 0.0
