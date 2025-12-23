from __future__ import annotations
from pathlib import Path
import sys
import os

# Add bundled binaries to PATH for PyInstaller frozen apps
if getattr(sys, 'frozen', False):
    # Running as compiled executable - add bundled binaries to PATH
    bundle_dir = getattr(sys, '_MEIPASS', None)
    if bundle_dir:
        os.environ['PATH'] = f"{bundle_dir}{os.pathsep}{os.environ.get('PATH', '')}"

# Import types (lightweight, no heavy dependencies)
from .transcriber_types import (
    Language, WhisperModel, DeviceType,
    DeviceInfo, TranscriptionSettings, TranscriptionMode
)

# Heavy dependencies - only imported here, not by UI
import whisper
import openai
import torch

# Qt imports for worker thread
from PySide6.QtCore import QThread, Signal


class TranscriptionWorker(QThread):
    """Worker thread for running transcription without blocking the UI."""

    finished = Signal(Path)                 # Emits the path to the output file
    error = Signal(str)                     # Emits error message if transcription fails
    progress = Signal(str)                  # Emits progress updates
    device_detected = Signal(DeviceInfo)    # Emits device info when detected

    def __init__(self, mode: TranscriptionMode, settings: TranscriptionSettings,
                 filepath: Path, api_key: str = "", model_type: WhisperModel = WhisperModel.BASE,
                 output_name: str = None):
        super().__init__()
        self.mode = mode
        self.settings = settings
        self.filepath = filepath
        self.api_key = api_key
        self.model_type = model_type
        self.output_name = output_name

    def run(self):
        """Execute transcription in a separate thread."""
        try:
            if self.mode == TranscriptionMode.ONLINE:
                if not self.api_key:
                    self.error.emit("API key is required for online transcription")
                    return
                output_path = Transcriber.transcribe_online(
                    self.settings, self.filepath, self.api_key,
                    progress_callback=self.progress.emit,
                    output_name=self.output_name
                )
            else:
                output_path, device_info = Transcriber.transcribe_offline(
                    self.settings, self.filepath, self.model_type,
                    progress_callback=self.progress.emit,
                    output_name=self.output_name
                )
                self.device_detected.emit(device_info)

            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(f"Transcription failed: {str(e)}")


class Transcriber:

    @staticmethod
    def detect_device() -> DeviceInfo:
        """
        Detects the best available compute device for Whisper transcription.

        Priority:
        1. CUDA (NVIDIA GPU on Windows/Linux)
        2. MPS (Apple Silicon GPU on macOS)
        3. CPU (fallback)

        Returns:
            DeviceInfo with device type, internal name, and display name
        """
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            return DeviceInfo(
                device="cuda",
                name="cuda",
                display_name=f"GPU (CUDA - {gpu_name})"
            )
        elif torch.backends.mps.is_available():
            return DeviceInfo(
                device="mps",
                name="mps",
                display_name="GPU (Metal - Apple Silicon)"
            )
        else:
            return DeviceInfo(
                device="cpu",
                name="cpu",
                display_name="CPU"
            )

    @staticmethod
    def transcribe_offline(settings: TranscriptionSettings, filepath: str, model_type: WhisperModel, progress_callback=None, output_name: str = None) -> tuple[Path, DeviceInfo]:
        """
        Transcribe audio using a local Whisper model.

        Args:
            settings: Transcription settings
            filepath: Path to audio file
            model_type: Whisper model to use
            progress_callback: Optional callback function for progress updates
            output_name: Optional custom name for output file (without extension)
        """
        def log(message: str):
            """Helper to print and optionally call progress callback."""
            print(message)
            if progress_callback:
                progress_callback(message)

        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        # Detect best available device
        device_info = Transcriber.detect_device()

        log(f"Loading Whisper model '{model_type.value}' on {device_info.display_name}...")

        # Get model directory from settings
        from .settings_view import SettingsHelper
        model_dir = SettingsHelper.get_model_directory()

        # Try with detected device first, fall back to CPU if it fails
        try:
            model = whisper.load_model(model_type.value, device=device_info.name, download_root=str(model_dir))

            log("Starting local transcription...")

            result = model.transcribe(
                str(file_path),
                language=None if settings.language == Language.AUTO else settings.language.value,
                initial_prompt=settings.initial_prompt,
            )
        except (RuntimeError, ValueError) as e:
            # MPS can produce NaN errors on Apple Silicon - fall back to CPU
            if device_info.device == "mps":
                log(f"⚠️  MPS failed with error, falling back to CPU: {e}")
                device_info = DeviceInfo(device="cpu", name="cpu", display_name="CPU (MPS fallback)")
                model = whisper.load_model(model_type.value, device="cpu", download_root=str(model_dir))
                result = model.transcribe(
                    str(file_path),
                    language=None if settings.language == Language.AUTO else settings.language.value,
                    initial_prompt=settings.initial_prompt,
                )
            else:
                raise

        # Use custom output name if provided, otherwise use input filename
        if output_name:
            output_path = file_path.parent / f"{output_name}.srt"
        else:
            output_path = file_path.parent / f"{file_path.name}.srt"

        log(f"Writing subtitles to {output_path.name}")

        Transcriber._write_srt(
            result["segments"],
            output_path,
            settings.max_line_count,
            settings.max_words_per_line
        )

        log("✓ Transcription complete!")

        return output_path, device_info

    @staticmethod
    def transcribe_online(settings: TranscriptionSettings, filepath: str, api_key: str, progress_callback=None, output_name: str = None) -> Path:
        """
        Transcribe audio using OpenAI's Whisper API.

        Args:
            settings: Transcription settings
            filepath: Path to audio file
            api_key: OpenAI API key
            progress_callback: Optional callback function for progress updates
            output_name: Optional custom name for output file (without extension)
        """
        def log(message: str):
            """Helper to print and optionally call progress callback."""
            print(message)
            if progress_callback:
                progress_callback(message)

        openai.api_key = api_key

        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        log("Uploading file to OpenAI Whisper API...")

        with open(file_path, "rb") as f:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                prompt=settings.initial_prompt or "",
                language=None if settings.language == Language.AUTO else settings.language.value,
                response_format="verbose_json"
            )

        log("Processing transcription from API...")

        # Convert TranscriptionSegment objects to dictionaries
        segments = [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text
            }
            for seg in response.segments
        ]

        # Use custom output name if provided, otherwise use input filename
        if output_name:
            output_path = file_path.parent / f"{output_name}.srt"
        else:
            output_path = file_path.parent / f"{file_path.name}.srt"

        log(f"Writing subtitles to {output_path.name}")

        Transcriber._write_srt(
            segments,
            output_path,
            settings.max_line_count,
            settings.max_words_per_line
        )

        log("✓ Transcription complete!")

        return output_path

    @staticmethod
    def _write_srt(segments: dict, output_path: Path, max_lines: int=1, max_words: int=8) -> None:
        """Converts Whisper segments to an SRT file."""
        def fmt_time(seconds: float) -> str:
            ms = int((seconds % 1) * 1000)
            h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        with open(output_path, "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, start=1):
                start = fmt_time(seg["start"])
                end = fmt_time(seg["end"])
                text = seg["text"].strip()

                # Simple line wrapping
                words = text.split()
                lines = []
                for j in range(0, len(words), max_words):
                    lines.append(" ".join(words[j:j + max_words]))
                if len(lines) > max_lines:
                    lines = [" ".join(words[:max_words * max_lines]) + " …"]

                f.write(f"{i}\n{start} --> {end}\n" + "\n".join(lines) + "\n\n")
