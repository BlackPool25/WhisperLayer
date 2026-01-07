"""Package entry point for running with python -m whisperlayer"""

import os

# Force XWayland for Qt overlay - fixes visibility issues on Ubuntu 24.04 Wayland
# This must be set BEFORE importing any Qt modules
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

# Set application name early
try:
    import gi
    gi.require_version('GLib', '2.0')
    from gi.repository import GLib
    GLib.set_prgname('whisperlayer')
    GLib.set_application_name('WhisperLayer')
except Exception as e:
    print(f"Warning: Could not set application name: {e}")

from .app import main

if __name__ == "__main__":
    main()
