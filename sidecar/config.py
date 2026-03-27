"""Application configuration and settings."""

from pathlib import Path
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
SIDECAR_DIR = PROJECT_ROOT / "sidecar"
AUDIO_HELPER_DIR = PROJECT_ROOT / "audio-helper"

SAMPLE_RATE = 16000


class LLMSettings(BaseModel):
    provider: str = "lmstudio"  # "lmstudio" (local) or "claude" (cloud)
    lmstudio_base_url: str = "http://localhost:1234"
    lmstudio_model: str = ""  # Empty = use whatever is loaded in LM Studio
    claude_api_key: str = ""
    claude_model: str = "claude-haiku-4-5-20251001"

class SuggestionSettings(BaseModel):
    max_suggestions: int = 5
    debounce_seconds: float = 8.0
    min_interval_seconds: float = 8.0

class AudioSettings(BaseModel):
    app_bundle_id: str | None = None  # None = all system audio
    microphone_device: int | None = None  # None = default
    capture_microphone: bool = False  # Disabled by default — only capture system audio

class Settings(BaseModel):
    llm: LLMSettings = LLMSettings()
    suggestions: SuggestionSettings = SuggestionSettings()
    audio: AudioSettings = AudioSettings()
    whisper_model: str = "ggml-large-v3.bin"
