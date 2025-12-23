from dataclasses import dataclass
from enum import Enum
from typing import Literal


class TranscriptionMode(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    
    
class Language(Enum):
    AUTO = "auto"
    DE = "de"
    EN = "en"
    FR = "fr"
    IT = "it"


class WhisperModel(Enum):
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


DeviceType = Literal["cuda", "mps", "cpu"]


@dataclass
class DeviceInfo:
    device: DeviceType
    name: str
    display_name: str


@dataclass
class TranscriptionSettings:
    language: Language = Language.DE
    max_line_count: int = 1
    max_words_per_line: int = 8
    initial_prompt: str | None = None

    def to_dict(self) -> dict:
        """Convert settings to a dictionary for storage."""
        return {
            "language": self.language.value,
            "max_line_count": self.max_line_count,
            "max_words_per_line": self.max_words_per_line,
            "initial_prompt": self.initial_prompt
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptionSettings":
        """Create settings from a dictionary, using defaults for missing values."""
        return cls(
            language=Language(data.get("language", Language.DE.value)),
            max_line_count=data.get("max_line_count", 1),
            max_words_per_line=data.get("max_words_per_line", 8),
            initial_prompt=data.get("initial_prompt", None)
        )
