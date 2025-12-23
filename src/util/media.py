"""
Media utilities for handling video and audio files.
"""
from __future__ import annotations
import subprocess
import sys
import os
from pathlib import Path
from typing import Tuple

# Add bundled binaries to PATH for PyInstaller frozen apps
if getattr(sys, 'frozen', False):
    # Running as compiled executable - add bundled binaries to PATH
    bundle_dir = getattr(sys, '_MEIPASS', None)
    if bundle_dir:
        os.environ['PATH'] = f"{bundle_dir}{os.pathsep}{os.environ.get('PATH', '')}"


class MediaHandler:
    """Handles video-to-audio conversion and temporary file management."""

    # Video file extensions
    VIDEO_EXTENSIONS = {'.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.m4v', '.wmv'}

    # Audio file extensions
    AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma'}

    @staticmethod
    def is_video_file(file_path: Path) -> bool:
        """Check if the file is a video file based on extension."""
        return file_path.suffix.lower() in MediaHandler.VIDEO_EXTENSIONS

    @staticmethod
    def is_audio_file(file_path: Path) -> bool:
        """Check if the file is an audio file based on extension."""
        return file_path.suffix.lower() in MediaHandler.AUDIO_EXTENSIONS

    @staticmethod
    def extract_audio_from_video(video_path: Path) -> Path:
        """
        Extract audio from a video file using ffmpeg.

        Args:
            video_path: Path to the input video file

        Returns:
            Path to the extracted audio file (WAV format)

        Raises:
            RuntimeError: If ffmpeg extraction fails
        """
        # Create output path next to original file with .temp_ prefix
        output_path = video_path.parent / f".temp_{video_path.stem}.wav"

        # Build ffmpeg command
        # -i: input file
        # -vn: disable video recording
        # -acodec pcm_s16le: use PCM 16-bit little-endian codec (uncompressed)
        # -ar 16000: sample rate 16kHz (good for speech recognition)
        # -ac 1: mono audio (reduces file size, sufficient for transcription)
        # -y: overwrite output file if it exists
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y',
            str(output_path)
        ]

        try:
            # Run ffmpeg and capture output
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )

            if not output_path.exists():
                raise RuntimeError("FFmpeg completed but output file was not created")

            return output_path

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"Failed to extract audio from video: {error_msg}")
        except FileNotFoundError:
            raise RuntimeError("FFmpeg not found. Please ensure FFmpeg is installed and in PATH.")

    @staticmethod
    def prepare_audio_file(file_path: Path) -> Tuple[Path, Path | None]:
        """
        Prepare an audio file for transcription.

        If the file is a video, extracts audio to a temporary file next to the original.
        If the file is already audio, returns it as-is.

        Args:
            file_path: Path to the media file (audio or video)

        Returns:
            Tuple of (audio_file_path, temp_file_path)
            - audio_file_path: Path to the audio file ready for transcription
            - temp_file_path: Path to temp file if created, None otherwise

        Raises:
            ValueError: If file type is not supported
            RuntimeError: If audio extraction fails
        """
        if MediaHandler.is_audio_file(file_path):
            # Already an audio file, use it directly
            return file_path, None

        elif MediaHandler.is_video_file(file_path):
            # Video file, need to extract audio
            audio_path = MediaHandler.extract_audio_from_video(file_path)
            return audio_path, audio_path

        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
