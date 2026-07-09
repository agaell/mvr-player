"""Video playback through an FFmpeg decoding process."""

from __future__ import annotations

import queue
import subprocess
import threading
import mmap
from collections import deque
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .ffmpeg_utils import MVR_SOURCE_FPS, FfmpegLookupError, find_ffmpeg, input_args_for_file

PLAYBACK_FPS = MVR_SOURCE_FPS


@dataclass(frozen=True)
class VideoFrame:
    """Decoded RGB video frame."""

    width: int
    height: int
    data: bytes


@dataclass(frozen=True)
class SeekPoint:
    """Byte offset for a decodable H.264 keyframe area."""

    seconds: float
    offset: int


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
        self.frame_queue: queue.Queue[VideoFrame] = queue.Queue(maxsize=12)
        self._process: subprocess.Popen[bytes] | None = None
        self._stdin_file: BinaryIO | None = None
        self._seek_points: list[SeekPoint] = []
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

    @property
    def output_size(self) -> tuple[int, int]:
        """Return the pixel size currently produced by the decoder."""
        return self._output_size

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
        self._seek_points = self._build_seek_points(self.file_path)
        return self.file_path

    def preview_frame(
        self,
        max_size: tuple[int, int],
        timeout: float = 10,
        start_seconds: float = 0.0,
    ) -> VideoFrame:
        """Decode one frame for immediate display after opening a file."""
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if not self.file_path.exists():
            raise PlayerFileError(f"Файл не найден: {self.file_path}")

        ffmpeg = self._find_ffmpeg()
        width, height = self._normalise_size(max_size)
        frame_size = width * height * 3
        input_args, input_handle, relative_start = self._input_args_for_start(start_seconds)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            *input_args,
            *self._seek_output_args(relative_start),
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
            input_context = input_handle if hasattr(input_handle, "__enter__") else nullcontext(input_handle)
            with input_context as stdin:
                result = subprocess.run(
                    command,
                    stdin=stdin,
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

    def play(self, max_size: tuple[int, int], start_seconds: float = 0.0) -> None:
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
        input_args, input_handle, relative_start = self._input_args_for_start(start_seconds)
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            *input_args,
            *self._seek_output_args(relative_start),
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
                stdin=input_handle,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            if hasattr(input_handle, "close"):
                input_handle.close()
            raise MvrPlayerError(f"Не удалось запустить FFmpeg: {exc}") from exc

        self._process = process
        self._stdin_file = input_handle if hasattr(input_handle, "close") else None
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
        self._close_stdin_file()
        self._clear_frames()

    def is_playing(self) -> bool:
        """Return whether FFmpeg is currently decoding."""
        self._refresh_process_state()
        return self._process is not None

    def read_frame(self) -> VideoFrame | None:
        """Return the next available decoded frame."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        """Release playback resources."""
        self.stop()

    def estimate_duration_seconds(self, fps: int = PLAYBACK_FPS, timeout: float = 15) -> float | None:
        """Estimate duration by counting source frames without re-encoding."""
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if not self.file_path.exists():
            raise PlayerFileError(f"Файл не найден: {self.file_path}")

        ffmpeg = self._find_ffmpeg()
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-progress",
            "pipe:1",
            *self._input_args(),
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-f",
            "null",
            "-",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return None
        except OSError as exc:
            raise MvrPlayerError(f"Не удалось запустить FFmpeg: {exc}") from exc

        if result.returncode != 0:
            return None

        frame_count = _parse_progress_frame_count(result.stdout)
        if frame_count <= 0 or fps <= 0:
            return None
        return frame_count / fps

    def _normalise_size(self, max_size: tuple[int, int]) -> tuple[int, int]:
        width = max(160, int(max_size[0]))
        height = max(120, int(max_size[1]))
        return width, height

    def _video_filter(self, width: int, height: int) -> str:
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={PLAYBACK_FPS}"
        )

    def _input_args(self) -> list[str]:
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        args = input_args_for_file(self.file_path)
        if self.file_path.suffix.lower() == ".mvr":
            return ["-r", str(PLAYBACK_FPS), *args]
        return args

    def _input_args_for_start(self, start_seconds: float) -> tuple[list[str], BinaryIO, float]:
        if self.file_path is None:
            raise PlayerFileError("Сначала выберите MVR-файл.")
        if self.file_path.suffix.lower() != ".mvr":
            return self._input_args(), subprocess.DEVNULL, start_seconds

        seek_point = self._seek_point_for_seconds(start_seconds)
        input_file = self.file_path.open("rb")
        input_file.seek(seek_point.offset)
        args = ["-r", str(PLAYBACK_FPS), "-f", "h264", "-i", "-"]
        return args, input_file, max(0.0, start_seconds - seek_point.seconds)

    def _seek_output_args(self, start_seconds: float) -> list[str]:
        start = max(0.0, float(start_seconds))
        if start <= 0:
            return []
        return ["-ss", f"{start:.3f}"]

    def _build_seek_points(self, file_path: Path) -> list[SeekPoint]:
        if file_path.suffix.lower() != ".mvr":
            return [SeekPoint(seconds=0.0, offset=0)]

        if file_path.stat().st_size == 0:
            return [SeekPoint(seconds=0.0, offset=0)]

        code3 = bytes([0, 0, 1])
        code4 = bytes([0, 0, 0, 1])
        points: list[SeekPoint] = []
        last_sequence_parameter_set_offset = 0
        frame_index = -1
        position = 0

        try:
            with file_path.open("rb") as stream:
                with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                    data_size = len(data)
                    while True:
                        three_byte_start = data.find(code3, position)
                        four_byte_start = data.find(code4, position)
                        if three_byte_start < 0 and four_byte_start < 0:
                            break
                        if four_byte_start >= 0 and (
                            three_byte_start < 0 or four_byte_start <= three_byte_start
                        ):
                            start = four_byte_start
                            header = start + 4
                        else:
                            start = three_byte_start
                            header = start + 3

                        if header < data_size:
                            nal_type = data[header] & 31
                            if nal_type == 7:
                                last_sequence_parameter_set_offset = start
                            elif nal_type in (1, 5):
                                frame_index += 1
                                if nal_type == 5:
                                    points.append(
                                        SeekPoint(
                                            seconds=max(0.0, frame_index / PLAYBACK_FPS),
                                            offset=last_sequence_parameter_set_offset or start,
                                        )
                                    )
                        position = header + 1
        except OSError:
            return [SeekPoint(seconds=0.0, offset=0)]

        if not points or points[0].seconds > 0:
            points.insert(0, SeekPoint(seconds=0.0, offset=0))
        return points

    def _seek_point_for_seconds(self, start_seconds: float) -> SeekPoint:
        target = max(0.0, float(start_seconds))
        point = self._seek_points[0] if self._seek_points else SeekPoint(seconds=0.0, offset=0)
        for candidate in self._seek_points:
            if candidate.seconds > target:
                break
            point = candidate
        return point

    def _find_ffmpeg(self) -> str:
        try:
            return find_ffmpeg(self.ffmpeg_path)
        except FfmpegLookupError as exc:
            raise FfmpegNotFoundError(str(exc)) from exc

    def _refresh_process_state(self) -> None:
        process = self._process
        if process is None:
            return
        returncode = process.poll()
        if returncode is not None:
            self._last_returncode = returncode
            self._process = None
            self._close_stdin_file()

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
        while not self._stop_requested:
            try:
                self.frame_queue.put(frame, timeout=0.1)
                return
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

    def _close_stdin_file(self) -> None:
        stdin_file = self._stdin_file
        self._stdin_file = None
        if stdin_file is not None and not stdin_file.closed:
            stdin_file.close()

def _parse_progress_frame_count(progress_output: str) -> int:
    frame_count = 0
    for line in progress_output.splitlines():
        if not line.startswith("frame="):
            continue
        try:
            frame_count = int(line.split("=", maxsplit=1)[1])
        except ValueError:
            pass
    return frame_count
