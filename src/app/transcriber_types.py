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
    TURBO = "turbo"
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
    max_line_count: int = 2
    max_line_width: int = 42
    initial_prompt: str | None = None
