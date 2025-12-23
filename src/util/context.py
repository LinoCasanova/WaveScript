from __future__ import annotations

import sys
import platform
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional
from types import MappingProxyType
from tomllib import load as tomlload
from PySide6.QtCore import QSettings


class Platform(Enum):
    """Supported platforms for WaveScript."""
    MACOS = "Darwin"
    WINDOWS = "Windows"
    LINUX = "Linux"

    @classmethod
    def current(cls) -> Platform:
        """Detect and return the current platform."""
        system = platform.system()
        if system == "Darwin":
            return cls.MACOS
        elif system == "Windows":
            return cls.WINDOWS
        else:
            return cls.LINUX


class _ConfigAccessor:
    """Accessor for config.toml values."""

    def __init__(self, config: Mapping[str, Any]):
        self._config = config

    def get(self, section: str | None, key: str, default: Any = None) -> Any:
        """
        Get a value from config.toml.

        Args:
            section: Section name (e.g., "app", "build") or None for top-level keys
            key: Key name within the section
            default: Default value if not found

        Examples:
            Context.Config.get("app", "name", "DefaultApp")
            Context.Config.get(None, "top_level_key", "default")
        """
        if section is None:
            return self._config.get(key, default)
        else:
            section_data = self._config.get(section, {})
            if isinstance(section_data, dict):
                return section_data.get(key, default)
            return default

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire section as a dictionary."""
        return dict(self._config.get(section, {}))

    def __getitem__(self, key: str) -> Any:
        """Dictionary-style access to top-level config values."""
        return self._config[key]

    def __contains__(self, key: str) -> bool:
        """Check if a top-level key exists in config."""
        return key in self._config


class _SettingsAccessor:
    """Accessor for QSettings persistent storage."""

    def __init__(self, qsettings: QSettings):
        self._qsettings = qsettings

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from QSettings."""
        return self._qsettings.value(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in QSettings."""
        self._qsettings.setValue(key, value)
        self._qsettings.sync()

    def delete(self, key: str) -> None:
        """Remove a value from QSettings."""
        self._qsettings.remove(key)
        self._qsettings.sync()

    def contains(self, key: str) -> bool:
        """Check if a key exists in QSettings."""
        return self._qsettings.contains(key)

    def clear(self) -> None:
        """Clear all QSettings values."""
        self._qsettings.clear()
        self._qsettings.sync()


class _ContextMeta(type):
    """Metaclass that enables class-level access to singleton instance attributes."""

    def __getattr__(cls, name: str) -> Any:
        """Delegate attribute access to the singleton instance."""
        instance = cls._get_instance()
        return getattr(instance, name)

    def _get_instance(cls) -> Context:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = super(_ContextMeta, cls).__call__()
        return cls._instance


class Context(metaclass=_ContextMeta):
    """
    Application context singleton providing access to config.toml and persistent settings.

    - Dev mode: reads config.toml from project root.
    - Frozen (PyInstaller) mode: locates packaged resources inside the bundle.
    - Values are loaded once on first access and then cached.
    - Access via class-level attributes (no instantiation needed).

    Usage:
        # Access config.toml values
        app_name = Context.Config.get("app_name", "default")

        # Access QSettings storage
        api_key = Context.Settings.get("api_key")
        Context.Settings.set("api_key", "new-key")

        # Platform and paths
        if Context.platform == Platform.MACOS:
            print(Context.assets_dir)
    """

    _instance: Optional[Context] = None

    Config: _ConfigAccessor
    Settings: _SettingsAccessor

    platform: Platform
    project_root: Path
    assets_dir: Path
    config_path: Path
    is_frozen: bool

    def __new__(cls) -> Context:
        """Ensure singleton pattern when instantiated directly."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        self.is_frozen = bool(getattr(sys, "frozen", False))
        self.platform = Platform.current()

        if self.is_frozen:
            # Runtime inside a bundled app - use _MEIPASS for extracted resources
            base_path = Path(getattr(sys, '_MEIPASS', Path(sys.argv[0]).parent))

            # PyInstaller extracts to _MEIPASS, where our bundled resources are
            self.project_root = base_path
            self.config_path = base_path / "config.toml"
            self.assets_dir = base_path / "resources" / "assets"

            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"config.toml not found at expected location: {self.config_path}"
                )
        else:
            # Development mode: repository layout
            self.project_root = Path(__file__).resolve().parents[2]
            self.config_path = self.project_root / "config.toml"
            self.assets_dir = self.project_root / "assets"

        # Load config.toml once (read-only)
        if not self.config_path.exists():
            raise FileNotFoundError(f"config.toml not found at: {self.config_path}")
        with open(self.config_path, "rb") as f:
            raw = tomlload(f)
        if not isinstance(raw, dict):
            raise ValueError("config.toml must contain a top-level table/object.")

        # Initialize accessors
        self.Config = _ConfigAccessor(MappingProxyType(dict(raw)))
        self.Settings = _SettingsAccessor(QSettings("WaveScript", "WaveScript"))
