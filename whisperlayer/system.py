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
            # Reduced chunk size for reliability
            chunk_size = 20
            total_chunks = (len(text) + chunk_size - 1) // chunk_size
            
            import time
            
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i+chunk_size]
                
                # ydotool type command
                # --key-delay: delay between key presses in ms
                # Increased to 15ms to prevent dropped characters
                result = subprocess.run(
                    [self._ydotool_path, "type", "--key-delay", "15", "--", chunk],
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
        Press a specific key or key combination.
        
        Args:
            key: Key to press (e.g., "Return", "ctrl+c", "alt+Tab")
            
        Returns:
            True if successful
        """
        if self._ydotool_path is None:
            return False
        
        # Mapping for key aliases to standard input names
        # ydotool generally accepts standard Linux input names (e.g. KEY_ENTER -> Enter)
        # We try to map common variations to the most standard name
        NAME_MAPPING = {
            # Modifiers - Keep as names (lowercase usually fine)
            "ctrl": "ctrl", "control": "ctrl", "leftctrl": "leftctrl", "rightctrl": "rightctrl",
            "shift": "shift", "leftshift": "leftshift", "rightshift": "rightshift",
            "alt": "alt", "leftalt": "leftalt", "rightalt": "rightalt",
            "super": "super", "meta": "super", "win": "super", "windows": "super",
            
            # Special keys - Use valid ydotool LOWERCASE names
            # Verified 'enter' works. 'Return' typed 'r'. '28' typed '2'.
            "return": "enter", "enter": "enter", "ret": "enter",
            "kp_enter": "kp_enter", # hoping this works, otherwise use 'enter'
            "backspace": "backspace", "back": "backspace",
            "tab": "tab",
            "escape": "escape", "esc": "escape",
            "space": "space",
            "capslock": "capslock", "caps": "capslock",
            "delete": "delete", "del": "delete",
            "insert": "insert", "ins": "insert",
            "home": "home", "end": "end",
            "pageup": "pageup", "page_up": "pageup", "prior": "pageup",
            "pagedown": "pagedown", "page_down": "pagedown", "next": "pagedown",
            "menu": "menu",
            
            # Arrow keys
            "up": "up", "down": "down", "left": "left", "right": "right",
            
            # Punctuation keys that might need specific names
            # (Simple chars like 'a', '1', '.' usually work as is)
            "plus": "plus",
            "minus": "minus",
            "asterisk": "asterisk",
            "slash": "slash",
            "equal": "equal",
            "comma": "comma",
            "period": "dot", "dot": "dot",
            "semicolon": "semicolon",
            "apostrophe": "apostrophe", "quote": "apostrophe",
            "grave": "grave",
            "backslash": "backslash",
            "leftbrace": "leftbrace", "bracketleft": "leftbrace",
            "rightbrace": "rightbrace", "bracketright": "rightbrace",
        }
        
        key_lower = key.lower().strip()
        
        try:
            # Parse key combination (e.g., "ctrl+shift+a")
            parts = [p.strip() for p in key_lower.replace("<", "").replace(">", "").split("+")]
            
            mapped_parts = []
            for part in parts:
                # Check mapping
                if part in NAME_MAPPING:
                    mapped = NAME_MAPPING[part]
                    print(f"DEBUG: Mapping '{part}' -> '{mapped}'")
                    mapped_parts.append(mapped)
                elif part.startswith("f") and part[1:].isdigit():
                    # F1-F12 need upper case usually? e.g. F1
                    mapped_parts.append(part.upper())
                else:
                    # Pass through single chars or unknown keys
                    mapped_parts.append(part)
            
            if not mapped_parts:
                return False
                
            # Reconstruct key combo for ydotool: "ctrl+shift+a"
            final_key = "+".join(mapped_parts)
            
            # Run ydotool key <key>
            # Add small delay just in case
            cmd = [self._ydotool_path, "key", "--key-delay", "20", final_key]
            
            print(f"DEBUG: ydotool cmd: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5
            )
            
            if result.returncode != 0:
                print(f"ydotool failed: {result.stderr}")
            
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
