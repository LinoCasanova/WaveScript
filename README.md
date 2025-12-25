# 🌊 WaveScript 📝

A desktop application to create SRT files using OpenAI's Whisper model.

## Features

- **Dual transcription modes**:  Offline (local Whisper models) or Online (OpenAI API)
- **Multiple file formats**: Supports audio (MP3, WAV, M4A, etc.) and video (MP4, MOV, AVI, etc.)
- **Automatic device detection**: Utilizes CUDA, Apple Silicon (MPS) or CPU
- **Built-in SRT editor**: Edit generated subtitles directly in the app

## GPU Support

- **Windows**: NVIDIA GPUs (CUDA)
- **macOS**: Apple Silicon M1/M2/M3/M4 chips (Metal)

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
2. Select your audio or video file
3. Choose a transcription mode (Offline/Online)
4. Click transcribe and wait for the SRT file to be generated

To use the app, make sure to download at least one whisper model for **offline mode** or configure your OpenAI API key for **online mode**. Both can be done inside the settings (⚙). 


## Building

To create a standalone executable:

```bash
uv run build
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
