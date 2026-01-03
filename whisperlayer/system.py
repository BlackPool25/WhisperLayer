"""Text injection using ydotool and active window detection."""

import subprocess
import os
import shutil
from typing import Optional

from . import config


class TextInjector:
    """Handles typing text into the active window using ydotool."""
    
    def __init__(self):
        self._ydotool_path = shutil.which("ydotool")
        self._xdotool_path = shutil.which("xdotool")
        self._kdotool_path = shutil.which("kdotool")
        
        if self._ydotool_path is None:
            print("Warning: ydotool not found. Text injection will not work.")
            print("Install with: sudo apt install ydotool")
    
    def type_text(self, text: str) -> bool:
        """
        Type text into the currently focused window.
        
        Args:
            text: Text to type
            
        Returns:
            True if successful, False otherwise
        """
        if not text or not text.strip():
            return False
            
        if self._ydotool_path is None:
            print("ydotool not available")
            return False
        
        try:
            # ydotool type command
            # --key-delay: delay between key presses in ms
            result = subprocess.run(
                [self._ydotool_path, "type", "--key-delay", "5", "--", text],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                print(f"ydotool stderr: {result.stderr}")
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("ydotool type timeout")
            return False
        except Exception as e:
            print(f"ydotool error: {e}")
            return False
    
    def type_key(self, key: str) -> bool:
        """
        Press a specific key.
        
        Args:
            key: Key to press (e.g., "enter", "backspace")
            
        Returns:
            True if successful
        """
        if self._ydotool_path is None:
            return False
            
        try:
            result = subprocess.run(
                [self._ydotool_path, "key", key],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"ydotool key error: {e}")
            return False


class WindowInfo:
    """Detects active window information."""
    
    def __init__(self):
        self._session_type = os.environ.get("XDG_SESSION_TYPE", "x11")
        self._desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        
        self._xdotool_path = shutil.which("xdotool")
        self._kdotool_path = shutil.which("kdotool")
    
    @property
    def is_wayland(self) -> bool:
        """Check if running under Wayland."""
        return self._session_type == "wayland"
    
    @property
    def is_kde(self) -> bool:
        """Check if running KDE Plasma."""
        return "kde" in self._desktop or "plasma" in self._desktop
    
    @property
    def is_gnome(self) -> bool:
        """Check if running GNOME."""
        return "gnome" in self._desktop
    
    def get_active_window_name(self) -> str:
        """
        Get the name/title of the currently active window.
        
        Returns:
            Window title or "Unknown Window" if detection fails
        """
        # Try X11 method first (works for X11 and some XWayland apps)
        if self._xdotool_path:
            try:
                result = subprocess.run(
                    [self._xdotool_path, "getactivewindow", "getwindowname"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass
        
        # Try KDE-specific method
        if self.is_wayland and self.is_kde and self._kdotool_path:
            try:
                # Get active window ID
                id_result = subprocess.run(
                    [self._kdotool_path, "getactivewindow"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if id_result.returncode == 0 and id_result.stdout.strip():
                    window_id = id_result.stdout.strip()
                    # Get window name
                    name_result = subprocess.run(
                        [self._kdotool_path, "getwindowname", window_id],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if name_result.returncode == 0 and name_result.stdout.strip():
                        return name_result.stdout.strip()
            except Exception:
                pass
        
        # Fallback
        return "Unknown Window"
    
    def get_session_info(self) -> str:
        """Get a string describing the current session."""
        return f"{self._session_type.upper()} / {self._desktop or 'Unknown DE'}"
