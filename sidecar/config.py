"""Application configuration and settings.

Settings persist to ~/.pat/settings.json between sessions.
"""

import json
import logging
from pathlib import Path
from pydantic import BaseModel

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
SIDECAR_DIR = PROJECT_ROOT / "sidecar"
AUDIO_HELPER_DIR = PROJECT_ROOT / "audio-helper"
SETTINGS_DIR = Path.home() / ".pat"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

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

    def save(self) -> None:
        """Persist settings to disk. API keys go to macOS Keychain."""
        try:
            SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            # Save API key to Keychain, not to disk
            if self.llm.claude_api_key:
                _keychain_set("pat-ai-claude-api-key", self.llm.claude_api_key)
            # Save everything else (without the API key) to JSON
            data = self.model_dump()
            data["llm"]["claude_api_key"] = ""  # Never write key to disk
            SETTINGS_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")

    @classmethod
    def load(cls) -> "Settings":
        """Load settings from disk. API keys loaded from macOS Keychain."""
        s = cls()
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text())
                s = cls.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load settings, using defaults: {e}")
        # Load API key from Keychain
        key = _keychain_get("pat-ai-claude-api-key")
        if key:
            s.llm.claude_api_key = key
        return s


def _keychain_set(service: str, value: str) -> None:
    """Store a value in macOS Keychain."""
    import subprocess
    # Delete existing entry first (ignore errors)
    subprocess.run(
        ["security", "delete-generic-password", "-s", service],
        capture_output=True,
    )
    subprocess.run(
        ["security", "add-generic-password", "-s", service, "-a", "pat-ai", "-w", value],
        capture_output=True, check=True,
    )


def _keychain_get(service: str) -> str | None:
    """Retrieve a value from macOS Keychain."""
    import subprocess
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", "pat-ai", "-w"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None
