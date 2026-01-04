"""Package entry point for running with python -m whisperlayer"""

import os

# Force XWayland for Qt overlay - fixes visibility issues on Ubuntu 24.04 Wayland
# This must be set BEFORE importing any Qt modules
if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"

from .app import main

if __name__ == "__main__":
    main()
