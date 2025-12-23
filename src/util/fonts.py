"""
Font utilities for loading custom fonts in the application.
"""
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from src.util.context import Context


def load_custom_fonts() -> None:
    """
    Load all custom fonts from the assets/fonts directory.

    This should be called early in the application initialization,
    before any UI is created.
    """
    fonts_dir = Context.assets_dir / "fonts"

    if not fonts_dir.exists():
        print(f"Warning: Fonts directory not found at {fonts_dir}")
        return

    # Load all .ttf and .otf font files
    font_files = list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf"))

    for font_file in font_files:
        font_id = QFontDatabase.addApplicationFont(str(font_file))

        if font_id == -1:
            print(f"Warning: Failed to load font: {font_file.name}")
        else:
            # Get the font family names that were loaded
            families = QFontDatabase.applicationFontFamilies(font_id)


def get_comfortaa_font(size: int = 10, weight: int = 400) -> str:
    """
    Get a CSS font-family string for Comfortaa with fallbacks.

    Args:
        size: Font size in pixels
        weight: Font weight (300=Light, 400=Regular, 600=SemiBold, 700=Bold)

    Returns:
        CSS font-family string with fallbacks
    """
    return f"font-family: 'Comfortaa', 'Arial', font-size: {size}px; font-weight: {weight};"
