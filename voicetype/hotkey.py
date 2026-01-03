"""Global hotkey handling with Wayland support using evdev."""

from pynput import keyboard
import threading
import os
from typing import Callable, Optional

from . import config


def is_wayland() -> bool:
    """Check if running under Wayland."""
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


class EvdevHotkeyManager:
    """
    Hotkey manager using evdev for true global hotkeys on Wayland.
    Reads directly from /dev/input/event* devices.
    """
    
    def __init__(self, on_toggle: Optional[Callable[[], None]] = None, hotkey: Optional[str] = None):
        self.on_toggle = on_toggle
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._keyboard_device = None
        
        # Use provided hotkey or get from settings
        from .settings import get_settings
        self._hotkey_str = hotkey or get_settings().hotkey
        self._modifiers, self._main_key = self._parse_hotkey(self._hotkey_str)
    
    def _parse_hotkey(self, hotkey_str: str) -> tuple[set[str], str]:
        """Parse hotkey string like '<ctrl>+<alt>+f' into modifiers and key."""
        parts = hotkey_str.lower().replace(">", "").replace("<", "").split("+")
        modifiers = set()
        main_key = ""
        
        for part in parts:
            if part in ("ctrl", "control"):
                modifiers.add("ctrl")
            elif part in ("alt",):
                modifiers.add("alt")
            elif part in ("shift",):
                modifiers.add("shift")
            elif part in ("super", "meta", "win"):
                modifiers.add("super")
            else:
                main_key = part
        
        return modifiers, main_key
    
    def _find_keyboard_device(self):
        """Find the keyboard input device - prefer physical keyboards."""
        try:
            import evdev
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
            
            # Priority: find actual keyboard, not virtual/software ones
            keyboard_candidates = []
            
            for device in devices:
                caps = device.capabilities()
                # Check if device has EV_KEY capability with keyboard keys
                if evdev.ecodes.EV_KEY in caps:
                    keys = caps[evdev.ecodes.EV_KEY]
                    # Check for common keyboard keys
                    if evdev.ecodes.KEY_A in keys and evdev.ecodes.KEY_ENTER in keys:
                        name_lower = device.name.lower()
                        # Skip virtual/software keyboards and mice
                        skip_keywords = ['solaar', 'virtual', 'mouse', 'touchpad', 'trackpad']
                        if any(kw in name_lower for kw in skip_keywords):
                            continue
                        # High priority for actual keyboards
                        if 'evision' in name_lower or 'rgb keyboard' in name_lower:
                            keyboard_candidates.insert(0, device)
                        elif 'keyboard' in name_lower:
                            keyboard_candidates.append(device)
            
            if keyboard_candidates:
                return keyboard_candidates[0]
                
        except Exception as e:
            print(f"Failed to find keyboard device: {e}")
        return None
    
    def start(self):
        """Start listening for hotkeys via evdev."""
        try:
            import evdev
        except ImportError:
            print("evdev not installed. Falling back to pynput (may not work on Wayland).")
            return self._start_pynput_fallback()
        
        self._keyboard_device = self._find_keyboard_device()
        if self._keyboard_device is None:
            print("Warning: Could not find keyboard device. Using pynput fallback.")
            return self._start_pynput_fallback()
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._evdev_loop, daemon=True)
        self._thread.start()
        print(f"Global hotkey registered (evdev): {config.HOTKEY}")
    
    def _evdev_loop(self):
        """Main loop reading keyboard events from evdev."""
        import evdev
        from evdev import ecodes
        
        # Map key names to evdev keycodes
        key_map = {
            'a': ecodes.KEY_A, 'b': ecodes.KEY_B, 'c': ecodes.KEY_C,
            'd': ecodes.KEY_D, 'e': ecodes.KEY_E, 'f': ecodes.KEY_F,
            'g': ecodes.KEY_G, 'h': ecodes.KEY_H, 'i': ecodes.KEY_I,
            'j': ecodes.KEY_J, 'k': ecodes.KEY_K, 'l': ecodes.KEY_L,
            'm': ecodes.KEY_M, 'n': ecodes.KEY_N, 'o': ecodes.KEY_O,
            'p': ecodes.KEY_P, 'q': ecodes.KEY_Q, 'r': ecodes.KEY_R,
            's': ecodes.KEY_S, 't': ecodes.KEY_T, 'u': ecodes.KEY_U,
            'v': ecodes.KEY_V, 'w': ecodes.KEY_W, 'x': ecodes.KEY_X,
            'y': ecodes.KEY_Y, 'z': ecodes.KEY_Z,
            '1': ecodes.KEY_1, '2': ecodes.KEY_2, '3': ecodes.KEY_3,
            '4': ecodes.KEY_4, '5': ecodes.KEY_5, '6': ecodes.KEY_6,
            '7': ecodes.KEY_7, '8': ecodes.KEY_8, '9': ecodes.KEY_9,
            '0': ecodes.KEY_0, 'space': ecodes.KEY_SPACE,
        }
        
        modifier_keys = {
            ecodes.KEY_LEFTCTRL, ecodes.KEY_RIGHTCTRL,
            ecodes.KEY_LEFTALT, ecodes.KEY_RIGHTALT,
            ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT,
            ecodes.KEY_LEFTMETA, ecodes.KEY_RIGHTMETA,
        }
        
        target_key = key_map.get(self._main_key, None)
        if target_key is None:
            print(f"Unknown key: {self._main_key}")
            return
        
        # Track modifier state
        active_modifiers = set()
        
        try:
            for event in self._keyboard_device.read_loop():
                if self._stop_event.is_set():
                    break
                    
                if event.type != ecodes.EV_KEY:
                    continue
                
                # Update modifier state
                if event.code == ecodes.KEY_LEFTCTRL or event.code == ecodes.KEY_RIGHTCTRL:
                    if event.value in (1, 2):  # pressed or held
                        active_modifiers.add("ctrl")
                    else:
                        active_modifiers.discard("ctrl")
                elif event.code == ecodes.KEY_LEFTALT or event.code == ecodes.KEY_RIGHTALT:
                    if event.value in (1, 2):
                        active_modifiers.add("alt")
                    else:
                        active_modifiers.discard("alt")
                elif event.code == ecodes.KEY_LEFTSHIFT or event.code == ecodes.KEY_RIGHTSHIFT:
                    if event.value in (1, 2):
                        active_modifiers.add("shift")
                    else:
                        active_modifiers.discard("shift")
                elif event.code == ecodes.KEY_LEFTMETA or event.code == ecodes.KEY_RIGHTMETA:
                    if event.value in (1, 2):
                        active_modifiers.add("super")
                    else:
                        active_modifiers.discard("super")
                
                # Check for hotkey press
                if event.code == target_key and event.value == 1:  # key down
                    if active_modifiers == self._modifiers:
                        if self.on_toggle:
                            self.on_toggle()
                            
        except Exception as e:
            print(f"evdev error: {e}")
    
    def _start_pynput_fallback(self):
        """Fallback to pynput for non-evdev systems."""
        def handle_hotkey():
            if self.on_toggle:
                self.on_toggle()
        
        self._pynput_listener = keyboard.GlobalHotKeys({
            self._hotkey_str: handle_hotkey
        })
        self._pynput_listener.start()
        print(f"Hotkey registered (pynput fallback): {self._hotkey_str}")
    
    def stop(self):
        """Stop listening for hotkeys."""
        self._stop_event.set()
        if self._keyboard_device:
            try:
                self._keyboard_device.close()
            except Exception:
                pass
        if hasattr(self, '_pynput_listener'):
            self._pynput_listener.stop()
    
    def wait(self):
        """Wait for the listener to finish."""
        if self._thread:
            self._thread.join()
        elif hasattr(self, '_pynput_listener'):
            self._pynput_listener.join()


class HotkeyManager:
    """Manages global hotkey detection - uses evdev on Wayland, pynput otherwise."""
    
    def __init__(self, on_toggle: Optional[Callable[[], None]] = None, hotkey: Optional[str] = None):
        self.on_toggle = on_toggle
        self.hotkey = hotkey
        
        # Use evdev on Wayland for true global hotkeys
        if is_wayland():
            self._impl = EvdevHotkeyManager(on_toggle=on_toggle, hotkey=hotkey)
        else:
            self._impl = PynputHotkeyManager(on_toggle=on_toggle, hotkey=hotkey)
    
    def start(self):
        """Start listening for hotkeys."""
        self._impl.start()
    
    def stop(self):
        """Stop listening for hotkeys."""
        self._impl.stop()
    
    def wait(self):
        """Wait for the listener to finish."""
        self._impl.wait()


class PynputHotkeyManager:
    """Hotkey manager using pynput (for X11)."""
    
    def __init__(self, on_toggle: Optional[Callable[[], None]] = None, hotkey: Optional[str] = None):
        self.on_toggle = on_toggle
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_running = False
        
        # Use provided hotkey or get from settings
        from .settings import get_settings
        self._hotkey_str = hotkey or get_settings().hotkey
    
    def start(self):
        """Start listening for hotkeys."""
        if self._is_running:
            return
        
        self._is_running = True
        
        def handle_hotkey():
            if self.on_toggle:
                self.on_toggle()
        
        self._listener = keyboard.GlobalHotKeys({
            self._hotkey_str: handle_hotkey
        })
        self._listener.start()
        print(f"Hotkey registered: {self._hotkey_str}")
    
    def stop(self):
        """Stop listening for hotkeys."""
        self._is_running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
    
    def wait(self):
        """Wait for the listener to finish."""
        if self._listener:
            self._listener.join()
