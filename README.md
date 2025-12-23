# 🌊 WaveScript

A desktop application for audio and video transcription using OpenAI's Whisper model.

## Features

- **Dual transcription modes**: Online (OpenAI API) or offline (local Whisper models)
- **Multiple file formats**: Supports audio (MP3, WAV, M4A, etc.) and video (MP4, MOV, AVI, etc.)
- **Automatic device detection**: Utilizes CUDA, Apple Silicon (MPS), or CPU
- **SRT subtitle generation**: Creates industry-standard subtitle files
- **Built-in SRT editor**: Edit generated subtitles directly in the app

## Installation

Requires Python 3.12 or higher.

```bash
# Install dependencies
uv sync

# Run the application
uv run run
```

## Usage

1. Launch WaveScript
2. Select transcription mode (Online/Offline)
3. Choose a Whisper model size
4. Select your audio or video file
5. Click transcribe and wait for the SRT file to be generated

For online mode, configure your OpenAI API key in Settings (⚙).

## Building

To create a standalone executable:

```bash
uv run build
```