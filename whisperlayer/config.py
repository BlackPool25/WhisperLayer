"""Configuration settings for WhisperLayer - loads from settings.py"""

from .settings import get_settings

# Get settings instance
_settings = get_settings()


# Expose settings as module-level constants (for backward compatibility)
def _get_hotkey():
    return _settings.hotkey

def _get_model():
    return _settings.model

def _get_device():
    device = _settings.device
    if device == "auto":
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device

def _get_language():
    return _settings.language

def _get_silence_duration():
    return _settings.silence_duration

def _get_input_device():
    return _settings.input_device


# Properties that update from settings
@property
def HOTKEY():
    return _get_hotkey()

# For modules that import directly, provide current values
HOTKEY = _settings.hotkey
WHISPER_MODEL = _settings.model
WHISPER_LANGUAGE = _settings.language
SILENCE_DURATION = _settings.silence_duration

# Audio settings (unchanged)
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5  # seconds
BUFFER_DURATION = 5.0  # Rolling buffer size in seconds
SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection

# Overlay settings (unchanged)
OVERLAY_WIDTH = 400
OVERLAY_HEIGHT = 120
OVERLAY_OPACITY = 0.9
OVERLAY_PADDING = 15
OVERLAY_CORNER_RADIUS = 12
OVERLAY_BG_COLOR = (0.12, 0.12, 0.12, 0.95)
OVERLAY_ACCENT_COLOR = (0.4, 0.6, 1.0)
OVERLAY_TEXT_COLOR = (1.0, 1.0, 1.0)
OVERLAY_RECORDING_COLOR = (1.0, 0.3, 0.3)


def reload_settings():
    """Reload settings from disk and update module variables."""
    global HOTKEY, WHISPER_MODEL, WHISPER_LANGUAGE, SILENCE_DURATION
    _settings.load()
    HOTKEY = _settings.hotkey
    WHISPER_MODEL = _settings.model
    WHISPER_LANGUAGE = _settings.language
    SILENCE_DURATION = _settings.silence_duration


def get_whisper_device():
    """Get the Whisper device (cuda or cpu)."""
    return _get_device()


def get_input_device():
    """Get the audio input device ID."""
    return _get_input_device()
