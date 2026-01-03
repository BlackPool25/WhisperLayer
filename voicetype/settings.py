"""Settings persistence for VoiceType."""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional
import sounddevice as sd


# Default settings
DEFAULTS = {
    "model": "turbo",
    "device": "auto",  # auto, cpu, cuda
    "input_device": None,  # None = default device (stores friendly name or id)
    "input_device_id": None,  # Actual sounddevice ID
    "hotkey": "<ctrl>+<alt>+f",
    "silence_duration": 1.5,
    "auto_start": False,
    "language": "en",
}

# Available Whisper models (from openai-whisper)
AVAILABLE_MODELS = [
    ("tiny", "Tiny (~1GB VRAM) - Fastest, lowest accuracy"),
    ("base", "Base (~1GB VRAM) - Fast, basic accuracy"),
    ("small", "Small (~2GB VRAM) - Good balance"),
    ("medium", "Medium (~5GB VRAM) - Better accuracy"),
    ("large", "Large (~10GB VRAM) - Best accuracy"),
    ("turbo", "Turbo (~6GB VRAM) - Fast + accurate (recommended)"),
]

# Just the model names for compatibility
AVAILABLE_MODEL_NAMES = [m[0] for m in AVAILABLE_MODELS]

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


def get_autostart_path() -> Path:
    """Get the path to the autostart .desktop file."""
    autostart_dir = Path.home() / ".config" / "autostart"
    autostart_dir.mkdir(parents=True, exist_ok=True)
    return autostart_dir / "voicetype.desktop"


def get_input_devices_raw() -> list[dict]:
    """Get list of available input devices from sounddevice (raw ALSA names)."""
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


def get_input_devices() -> list[dict]:
    """
    Get list of available input devices with friendly names.
    Uses PulseAudio/PipeWire to get human-readable device names.
    Also detects Bluetooth devices that can switch to HSP/HFP mode for mic.
    Falls back to raw sounddevice names if pulsectl is unavailable.
    """
    devices = [{"id": None, "name": "Default System Microphone", "friendly_name": "Default System Microphone"}]
    seen_bluetooth = set()  # Track which BT devices we've already added as inputs
    
    try:
        import pulsectl
        
        with pulsectl.Pulse('voicetype-device-enum') as pulse:
            sources = pulse.source_list()
            
            for source in sources:
                # Skip monitor devices (they capture system audio, not mic)
                if '.monitor' in source.name:
                    continue
                
                friendly_name = source.description
                device_name = source.name
                
                # Track Bluetooth input devices we've seen
                if 'bluez' in source.name:
                    # Extract the MAC-based identifier
                    parts = source.name.split('.')
                    if len(parts) >= 2:
                        seen_bluetooth.add(parts[1])
                
                # Try to find the matching sounddevice ID
                sd_devices = sd.query_devices()
                matched_id = None
                
                # Get ALSA card/device info from PulseAudio properties
                props = source.proplist
                alsa_card = props.get('alsa.card')
                alsa_device = props.get('alsa.device', '0')
                
                if alsa_card is not None:
                    # Search for matching sounddevice entry
                    pattern = f"hw:{alsa_card},{alsa_device}"
                    for i, sd_dev in enumerate(sd_devices):
                        if sd_dev['max_input_channels'] > 0:
                            if pattern in sd_dev['name'] or alsa_card in sd_dev['name']:
                                matched_id = i
                                break
                
                # If no ALSA match, try matching by partial name
                if matched_id is None:
                    for i, sd_dev in enumerate(sd_devices):
                        if sd_dev['max_input_channels'] > 0:
                            # Try to match by keywords in the name
                            sd_name_lower = sd_dev['name'].lower()
                            friendly_lower = friendly_name.lower()
                            # Check if key words match
                            for keyword in ['usb', 'bluetooth', 'headset', 'microphone', 'webcam']:
                                if keyword in sd_name_lower and keyword in friendly_lower:
                                    matched_id = i
                                    break
                            if matched_id:
                                break
                
                devices.append({
                    "id": matched_id,
                    "name": device_name,
                    "friendly_name": friendly_name,
                    "pulse_source": source.name,
                })
            
            # Check for Bluetooth devices that could provide mic input if switched to HSP/HFP
            for card in pulse.card_list():
                if 'bluez' not in card.name:
                    continue
                
                # Extract MAC identifier from card name
                parts = card.name.split('.')
                mac_id = parts[1] if len(parts) >= 2 else card.name
                
                # Check if this device has HSP/HFP profile (headset mode with mic)
                has_hfp = any('headset' in p.name.lower() for p in card.profile_list)
                
                # Check if we already have an input from this Bluetooth device
                already_has_input = mac_id in seen_bluetooth
                
                if has_hfp:
                    bt_name = card.proplist.get('device.description', 'Bluetooth Device')
                    active_profile = card.profile_active.name if card.profile_active else ''
                    
                    if already_has_input:
                        # Already showing as input source, no need to add again
                        continue
                    
                    # Add as a potential device (user needs to switch profile in system settings)
                    if 'a2dp' in active_profile.lower():
                        # Currently in A2DP mode - show note about switching
                        devices.append({
                            "id": None,
                            "name": f"bluetooth:{card.name}",
                            "friendly_name": f"🎧 {bt_name} (switch to Headset mode in Sound Settings)",
                            "bluetooth_card": card.name,
                            "needs_profile_switch": True,
                        })
                
    except ImportError:
        # pulsectl not available, fall back to raw device names
        print("Warning: pulsectl not installed. Using raw device names.")
        print("Install with: pip install pulsectl")
        
        for dev in get_input_devices_raw():
            devices.append({
                "id": dev['id'],
                "name": dev['name'],
                "friendly_name": dev['name'],
            })
    except Exception as e:
        print(f"Error enumerating audio devices: {e}")
        # Fall back to raw names
        for dev in get_input_devices_raw():
            devices.append({
                "id": dev['id'],
                "name": dev['name'],
                "friendly_name": dev['name'],
            })
    
    return devices


def set_autostart_enabled(enabled: bool) -> bool:
    """
    Enable or disable autostart by creating/removing the .desktop file.
    Returns True if successful.
    """
    desktop_path = get_autostart_path()
    
    if enabled:
        # Create autostart entry
        import sys
        
        # Detect the executable path
        if os.environ.get("APPIMAGE"):
            exec_cmd = os.environ.get("APPIMAGE")
        elif os.environ.get("FLATPAK_ID"):
            exec_cmd = f"flatpak run {os.environ.get('FLATPAK_ID')}"
        else:
            # Standard Python installation - use python -m voicetype
            exec_cmd = f"{sys.executable} -m voicetype"
        
        desktop_content = f"""[Desktop Entry]
Type=Application
Name=VoiceType
Comment=Linux Native Speech-to-Text Voice Typing
Exec={exec_cmd}
Icon=audio-input-microphone
Categories=Utility;Accessibility;
X-GNOME-Autostart-enabled=true
Terminal=false
StartupNotify=false
"""
        try:
            desktop_path.write_text(desktop_content)
            return True
        except Exception as e:
            print(f"Failed to create autostart file: {e}")
            return False
    else:
        # Remove autostart entry
        try:
            if desktop_path.exists():
                desktop_path.unlink()
            return True
        except Exception as e:
            print(f"Failed to remove autostart file: {e}")
            return False


def is_autostart_enabled() -> bool:
    """Check if autostart is currently enabled."""
    return get_autostart_path().exists()


class Settings:
    """Manages application settings with persistence and live updates."""
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one settings instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._settings = DEFAULTS.copy()
        self._callbacks: list[callable] = []
        self._change_handlers: dict[str, list[callable]] = {}
        self.load()
        
        # Sync auto_start with actual file state
        self._settings['auto_start'] = is_autostart_enabled()
    
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
                print(f"Settings loaded from {config_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load settings: {e}")
    
    def save(self) -> None:
        """Save settings to file."""
        config_path = get_config_path()
        try:
            with open(config_path, 'w') as f:
                json.dump(self._settings, f, indent=2)
            print(f"Settings saved to {config_path}")
        except IOError as e:
            print(f"Warning: Could not save settings: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any, save: bool = True, notify: bool = True) -> None:
        """Set a setting value."""
        if key in DEFAULTS or key in ['input_device_id']:
            old_value = self._settings.get(key)
            self._settings[key] = value
            
            # Handle auto_start specially
            if key == 'auto_start':
                set_autostart_enabled(value)
            
            if save:
                self.save()
            
            if notify and old_value != value:
                self._notify_callbacks(key, value)
                self._notify_change_handlers(key, value, old_value)
    
    def get_all(self) -> dict:
        """Get all settings."""
        return self._settings.copy()
    
    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self._settings = DEFAULTS.copy()
        self.save()
        set_autostart_enabled(False)
    
    def add_callback(self, callback: callable) -> None:
        """Add a callback to be notified when any setting changes."""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: callable) -> None:
        """Remove a callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def on_change(self, key: str, handler: callable) -> None:
        """Register a handler for changes to a specific setting."""
        if key not in self._change_handlers:
            self._change_handlers[key] = []
        self._change_handlers[key].append(handler)
    
    def off_change(self, key: str, handler: callable) -> None:
        """Unregister a handler for a specific setting."""
        if key in self._change_handlers and handler in self._change_handlers[key]:
            self._change_handlers[key].remove(handler)
    
    def _notify_callbacks(self, key: str, value: Any) -> None:
        """Notify all callbacks of a setting change."""
        for callback in self._callbacks:
            try:
                callback(key, value)
            except Exception as e:
                print(f"Settings callback error: {e}")
    
    def _notify_change_handlers(self, key: str, new_value: Any, old_value: Any) -> None:
        """Notify handlers registered for a specific setting."""
        if key in self._change_handlers:
            for handler in self._change_handlers[key]:
                try:
                    handler(new_value, old_value)
                except Exception as e:
                    print(f"Settings change handler error for {key}: {e}")
    
    # Convenience properties
    @property
    def model(self) -> str:
        return self.get("model", "turbo")
    
    @property
    def device(self) -> str:
        return self.get("device", "auto")
    
    @property
    def input_device(self) -> Optional[int]:
        return self.get("input_device_id")
    
    @property
    def input_device_name(self) -> Optional[str]:
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
    """Get the global settings instance (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
