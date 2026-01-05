"""Global hotkey handling with Wayland support using evdev."""

from pynput import keyboard
import threading
import os
from typing import Callable, Optional

from . import config


def is_wayland() -> bool:
    """Check if running under Wayland."""
    return os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"


def get_keyboard_devices() -> list[dict]:
    """
    Get list of available keyboard input devices for user selection.
    Returns list of dicts with 'path', 'name', and 'friendly_name' keys.
    
    This function is compatible with any Linux system running evdev.
    Gaming keyboards often expose multiple input devices (for media keys,
    RGB control, macro keys, etc.) - all valid keyboard devices are listed.
    """
    devices = []
    
    # Add auto-detect option first
    devices.append({
        "path": "",  # Empty string means auto-detect
        "name": "auto",
        "friendly_name": "Auto-detect (recommended)",
    })
    
    try:
        import evdev
        
        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                caps = device.capabilities()
                
                # Check if device has keyboard capabilities
                if evdev.ecodes.EV_KEY in caps:
                    keys = caps[evdev.ecodes.EV_KEY]
                    # Must have letter keys and enter - filters out media remotes etc
                    if evdev.ecodes.KEY_A in keys and evdev.ecodes.KEY_ENTER in keys:
                        name_lower = device.name.lower()
                        
                        # Skip obvious non-keyboards
                        skip_keywords = ['solaar', 'virtual', 'mouse', 'touchpad', 'trackpad', 
                                        'consumer control', 'system control', 'power button', 
                                        'sleep button', 'video bus']
                        if any(kw in name_lower for kw in skip_keywords):
                            continue
                        
                        # Extract event number from path for disambiguation
                        # e.g., /dev/input/event5 -> event5
                        event_num = path.split('/')[-1] if '/' in path else path
                        
                        # Create user-friendly name with event number
                        friendly_name = device.name
                        if 'keyboard' not in name_lower:
                            friendly_name = f"{device.name} (Keyboard)"
                        # Add event number for disambiguation when multiple same-named devices exist
                        friendly_name = f"{friendly_name} [{event_num}]"
                        
                        devices.append({
                            "path": device.path,
                            "name": device.name,
                            "friendly_name": friendly_name,
                        })
                        
            except (PermissionError, OSError):
                # Can't access this device, skip it
                continue
                
    except ImportError:
        print("evdev not installed - keyboard device enumeration unavailable")
    except Exception as e:
        print(f"Error enumerating keyboard devices: {e}")
    
    return devices


class EvdevHotkeyManager:
    """
    Hotkey manager using evdev for true global hotkeys on Wayland.
    Reads directly from /dev/input/event* devices.
    """
    
    def __init__(self, on_toggle: Optional[Callable[[], None]] = None, hotkey: Optional[str] = None):
        self.on_toggle = on_toggle
        self._stop_event = threading.Event()
        self._paused = False  # Pause hotkey detection without stopping thread
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
        """Find the keyboard input device - uses saved setting or auto-detects."""
        try:
            import evdev
            
            # First, check if user has configured a specific keyboard device
            from .settings import get_settings
            settings = get_settings()
            saved_device_path = settings.get("keyboard_device")
            
            if saved_device_path:
                try:
                    device = evdev.InputDevice(saved_device_path)
                    caps = device.capabilities()
                    # Verify it's still a keyboard
                    if evdev.ecodes.EV_KEY in caps:
                        keys = caps[evdev.ecodes.EV_KEY]
                        if evdev.ecodes.KEY_A in keys and evdev.ecodes.KEY_ENTER in keys:
                            print(f"Using saved keyboard device: {device.name} ({saved_device_path})")
                            return device
                except (FileNotFoundError, PermissionError, OSError) as e:
                    print(f"Saved keyboard device not available: {e}")
                    print("Falling back to auto-detection...")
            
            # Auto-detect keyboard device
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
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
                        skip_keywords = ['solaar', 'virtual', 'mouse', 'touchpad', 'trackpad', 
                                         'consumer control', 'system control', 'power button']
                        if any(kw in name_lower for kw in skip_keywords):
                            continue
                        # Prioritize devices with 'keyboard' in the name
                        if 'keyboard' in name_lower:
                            keyboard_candidates.insert(0, device)
                        else:
                            keyboard_candidates.append(device)
            
            if keyboard_candidates:
                selected = keyboard_candidates[0]
                print(f"Auto-detected keyboard: {selected.name} ({selected.path})")
                return selected
                
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
        import select
        
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
            # Use select() for non-blocking reads so we can check stop_event
            while not self._stop_event.is_set():
                # Wait for device to be readable with timeout
                r, _, _ = select.select([self._keyboard_device.fd], [], [], 0.1)
                if not r:
                    continue  # Timeout, check stop_event again
                
                # Read available events (non-blocking since select said ready)
                for event in self._keyboard_device.read():
                    if self._stop_event.is_set():
                        return
                        
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
                    
                    # Check for hotkey press (skip if paused)
                    if event.code == target_key and event.value == 1:  # key down
                        if active_modifiers == self._modifiers:
                            if self.on_toggle and not self._paused:
                                self.on_toggle()
                            
        except Exception as e:
            if self._stop_event.is_set():
                # Expected error when stopping
                return
            print(f"evdev error: {e}")
    
    def _start_pynput_fallback(self):
        """Fallback to pynput for non-evdev systems."""
        def handle_hotkey():
            if self.on_toggle and not self._paused:
                self.on_toggle()
        
        self._pynput_listener = keyboard.GlobalHotKeys({
            self._hotkey_str: handle_hotkey
        })
        self._pynput_listener.start()
        print(f"Hotkey registered (pynput fallback): {self._hotkey_str}")
    
    def pause(self):
        """Pause hotkey detection (thread-safe, no stop/start)."""
        self._paused = True
    
    def resume(self):
        """Resume hotkey detection."""
        self._paused = False
    
    def update_hotkey(self, new_hotkey: str):
        """Update the hotkey configuration (thread-safe)."""
        self._hotkey_str = new_hotkey
        self._modifiers, self._main_key = self._parse_hotkey(new_hotkey)
        print(f"Hotkey updated to: {new_hotkey}")
    
    def stop(self):
        """Stop listening for hotkeys."""
        self._stop_event.set()
        # Wait for the thread to exit cleanly (it checks stop_event every 0.1s)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        # Now safe to close the device
        if self._keyboard_device:
            try:
                self._keyboard_device.close()
            except Exception:
                pass
            self._keyboard_device = None
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
    
    def pause(self):
        """Pause hotkey detection (thread-safe)."""
        self._impl.pause()
    
    def resume(self):
        """Resume hotkey detection."""
        self._impl.resume()
    
    def update_hotkey(self, new_hotkey: str):
        """Update the hotkey configuration (thread-safe)."""
        self._impl.update_hotkey(new_hotkey)
    
    def wait(self):
        """Wait for the listener to finish."""
        self._impl.wait()


class PynputHotkeyManager:
    """Hotkey manager using pynput (for X11)."""
    
    def __init__(self, on_toggle: Optional[Callable[[], None]] = None, hotkey: Optional[str] = None):
        self.on_toggle = on_toggle
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._is_running = False
        self._paused = False  # Pause hotkey detection without stopping
        
        # Use provided hotkey or get from settings
        from .settings import get_settings
        self._hotkey_str = hotkey or get_settings().hotkey
    
    def start(self):
        """Start listening for hotkeys."""
        if self._is_running:
            return
        
        self._is_running = True
        
        def handle_hotkey():
            if self.on_toggle and not self._paused:
                self.on_toggle()
        
        self._listener = keyboard.GlobalHotKeys({
            self._hotkey_str: handle_hotkey
        })
        self._listener.start()
        print(f"Hotkey registered: {self._hotkey_str}")
    
    def pause(self):
        """Pause hotkey detection (thread-safe)."""
        self._paused = True
    
    def resume(self):
        """Resume hotkey detection."""
        self._paused = False
    
    def update_hotkey(self, new_hotkey: str):
        """Update the hotkey - for pynput this requires restart but we update the string."""
        self._hotkey_str = new_hotkey
        # Note: pynput GlobalHotKeys doesn't support dynamic updates,
        # but evdev (primary on Wayland) does. For X11, we'd need to restart.
        print(f"Hotkey updated to: {new_hotkey} (pynput - may require app restart)")
    
    
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
