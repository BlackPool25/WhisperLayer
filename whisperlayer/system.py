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
            # Chunk long text to prevent ydotool timeouts/buffering issues
            chunk_size = 50
            total_chunks = (len(text) + chunk_size - 1) // chunk_size
            
            import time
            
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                
                # ydotool type command
                # --key-delay: delay between key presses in ms
                result = subprocess.run(
                    [self._ydotool_path, "type", "--key-delay", "5", "--", chunk],
                    capture_output=True,
                    text=True,
                    timeout=5  # Shorter timeout per chunk
                )
                
                if result.returncode != 0:
                    print(f"ydotool stderr (chunk {i//chunk_size + 1}/{total_chunks}): {result.stderr}")
                    return False
                
                # Small delay between chunks to let system catch up
                if total_chunks > 1:
                    time.sleep(0.05)
            
            return True
            
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
            key: Key to press (e.g., "Return", "BackSpace", "Tab")
            
        Returns:
            True if successful
        """
        if self._ydotool_path is None:
            return False
        
        # Map key names to Linux keycodes for ydotool
        # Format: ["keycode:1", "keycode:0"] for press and release
        key_map = {
            "return": ["28:1", "28:0"],
            "enter": ["28:1", "28:0"],
            "backspace": ["14:1", "14:0"],
            "tab": ["15:1", "15:0"],
            "escape": ["1:1", "1:0"],
            "space": ["57:1", "57:0"],
            # Modifier combinations
            "ctrl+c": ["29:1", "46:1", "46:0", "29:0"],
            "ctrl+v": ["29:1", "47:1", "47:0", "29:0"],
            "ctrl+x": ["29:1", "45:1", "45:0", "29:0"],
            "ctrl+z": ["29:1", "44:1", "44:0", "29:0"],
            "ctrl+a": ["29:1", "30:1", "30:0", "29:0"],
            "ctrl+shift+z": ["29:1", "42:1", "44:1", "44:0", "42:0", "29:0"],
            "ctrl+backspace": ["29:1", "14:1", "14:0", "29:0"],
        }
        
        key_lower = key.lower()
        
        try:
            if key_lower in key_map:
                keycodes = key_map[key_lower]
            else:
                # Try to use the key directly as a single keycode
                keycodes = [key]
            
            # Build command: ydotool key <keycode1> <keycode2> ...
            cmd = [self._ydotool_path, "key"] + keycodes
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            print(f"ydotool key error: {e}")
            return False
            
    def get_clipboard_text(self) -> str:
        """
        Get text from the system clipboard.
        
        Returns:
            Clipboard text or empty string if failed.
        """
        try:
            from PyQt5.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            return clipboard.text()
        except Exception as e:
            print(f"Clipboard error: {e}")
            return ""


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
