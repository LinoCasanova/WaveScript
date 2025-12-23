"""
Main entry point and application UI for WaveScript.
"""
from __future__ import annotations

import sys
import multiprocessing
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget

from src.util.context import Context
from src.util.fonts import load_custom_fonts
from src.app.transcriber_ui import TranscriberUI


def run_main_app(app: QApplication) -> int:
    """
    Run the main WaveScript application.

    Args:
        app: The QApplication instance

    Returns:
        Exit code from app.exec()
    """
    # Load stylesheet
    style_file = Context.assets_dir / "style.qss"
    if style_file.exists():
        try:
            app.setStyleSheet(style_file.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")

    # Create and configure main window
    win: QWidget = TranscriberUI()
    win.setWindowTitle(f"{Context.Config.get('app', 'name', 'App')} - Audio Transcriber")

    # Set application icon
    icon_path = Context.assets_dir / 'icons' / ("app.icns" if sys.platform == "darwin" else "app.ico")
    if icon_path.exists():
        win.setWindowIcon(QIcon(str(icon_path)))

    win.show()
    return app.exec()


def main() -> None:
    """
    Main entry point for WaveScript.

    All dependencies are bundled, so just launch the app directly.
    """
    # Required for PyInstaller + multiprocessing on macOS/Windows
    # Prevents spawning multiple app instances when using torch/whisper
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)
    app.setApplicationName(Context.Config.get("app", "name", "App"))
    app.setOrganizationName(Context.Config.get("app", "organization", "Org"))

    # Load custom fonts before creating any UI
    load_custom_fonts()

    # Launch the main application
    sys.exit(run_main_app(app))


if __name__ == "__main__":
    main()
