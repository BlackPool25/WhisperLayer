"""Settings persistence for VoiceType."""

import json
import os
from pathlib import Path
from typing import Any, Optional
import sounddevice as sd


# Default settings
DEFAULTS = {
    "model": "turbo",
    "device": "auto",  # auto, cpu, cuda
    "input_device": None,  # None = default device
    "hotkey": "<ctrl>+<alt>+f",
    "silence_duration": 1.5,
    "auto_start": False,
    "language": "en",
}

# Available models
AVAILABLE_MODELS = ["turbo", "large", "medium", "small", "base", "tiny"]

# Device options
DEVICE_OPTIONS = ["auto", "cpu", "cuda"]


def get_config_dir() -> Path:
    """Get the configuration directory, creating if needed."""
    config_dir = Path.home() / ".config" / "voicetype"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the settings file."""
    return get_config_dir() / "settings.json"


def get_input_devices() -> list[dict]:
    """Get list of available input devices."""
    devices = []
    try:
        for i, device in enumerate(sd.query_devices()):
            if device['max_input_channels'] > 0:
                devices.append({
                    "id": i,
                    "name": device['name'],
                    "channels": device['max_input_channels'],
                })
    except Exception:
        pass
    return devices


class Settings:
    """Manages application settings with persistence."""
    
    def __init__(self):
        self._settings = DEFAULTS.copy()
        self._callbacks: list[callable] = []
        self.load()
    
    def load(self) -> None:
        """Load settings from file."""
        config_path = get_config_path()
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    saved = json.load(f)
                # Merge with defaults (handles new settings)
                for key, value in saved.items():
                    if key in DEFAULTS:
                        self._settings[key] = value
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load settings: {e}")
    
    def save(self) -> None:
        """Save settings to file."""
        config_path = get_config_path()
        try:
            with open(config_path, 'w') as f:
                json.dump(self._settings, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any, save: bool = True) -> None:
        """Set a setting value."""
        if key in DEFAULTS:
            self._settings[key] = value
            if save:
                self.save()
            self._notify_callbacks(key, value)
    
    def get_all(self) -> dict:
        """Get all settings."""
        return self._settings.copy()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = DEFAULTS.copy()
        self.save()
    
    def add_callback(self, callback: callable) -> None:
        """Add a callback to be notified when settings change."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: callable) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def _notify_callbacks(self, key: str, value: Any) -> None:
        """Notify all callbacks of a setting change."""
        for callback in self._callbacks:
            try:
                callback(key, value)
            except Exception as e:
                print(f"Settings callback error: {e}")
    
    # Convenience properties
    @property
    def model(self) -> str:
        return self.get("model", "turbo")
    
    @property
    def device(self) -> str:
        return self.get("device", "auto")
    
    @property
    def input_device(self) -> Optional[int]:
        return self.get("input_device")
    
    @property
    def hotkey(self) -> str:
        return self.get("hotkey", "<ctrl>+<alt>+f")
    
    @property
    def silence_duration(self) -> float:
        return self.get("silence_duration", 1.5)
    
    @property
    def auto_start(self) -> bool:
        return self.get("auto_start", False)
    
    @property
    def language(self) -> str:
        return self.get("language", "en")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
