"""System tray integration for WhisperLayer using GTK3 AppIndicator."""

import gi
gi.require_version('Gtk', '3.0')
try:
    gi.require_version('AppIndicator3', '0.1')
    HAS_APPINDICATOR = True
except ValueError:
    HAS_APPINDICATOR = False

from gi.repository import Gtk, GLib
if HAS_APPINDICATOR:
    from gi.repository import AppIndicator3

import threading
import os
import signal
import sys
from typing import Callable, Optional
from pathlib import Path


class SystemTray:
    """System tray icon with menu."""
    
    def __init__(
        self,
        on_toggle: Optional[Callable[[], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
        on_quit: Optional[Callable[[], None]] = None
    ):
        self.on_toggle = on_toggle
        self.on_settings = on_settings
        self.on_quit = on_quit
        
        self._is_recording = False
        self._indicator = None
        self._menu = None
        self._toggle_item = None
        self._gtk_thread: Optional[threading.Thread] = None
        self._running = False
        self._main_context = None
    
    def _create_menu(self) -> Gtk.Menu:
        """Create the tray menu."""
        menu = Gtk.Menu()
        
        # Toggle recording - most prominent action
        self._toggle_item = Gtk.MenuItem(label="🎤 Start Recording")
        self._toggle_item.connect("activate", self._on_toggle_clicked)
        menu.append(self._toggle_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Settings
        settings_item = Gtk.MenuItem(label="⚙️ Settings")
        settings_item.connect("activate", self._on_settings_clicked)
        menu.append(settings_item)
        
        # About
        about_item = Gtk.MenuItem(label="ℹ️ About")
        about_item.connect("activate", self._on_about_clicked)
        menu.append(about_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit - clear and at the bottom
        quit_item = Gtk.MenuItem(label="❌ Quit WhisperLayer")
        quit_item.connect("activate", self._on_quit_clicked)
        menu.append(quit_item)
        
        menu.show_all()
        return menu
    
    def _on_toggle_clicked(self, widget):
        """Handle toggle menu item click."""
        print("Tray: Toggle recording clicked")
        if self.on_toggle:
            # Run in main thread to avoid GTK threading issues
            threading.Thread(target=self.on_toggle, daemon=True).start()
    
    def _on_settings_clicked(self, widget):
        """Handle settings menu item click."""
        print("Tray: Settings clicked")
        if self.on_settings:
            GLib.idle_add(self.on_settings)
    
    def _on_about_clicked(self, widget):
        """Show about dialog."""
        def show_dialog():
            dialog = Gtk.MessageDialog(
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="WhisperLayer"
            )
            dialog.format_secondary_text(
                "Linux Native Speech-to-Text Voice Typing\n\n"
                "Press your hotkey to start/stop recording.\n"
                "Transcribed text will be typed automatically.\n\n"
                "Version 1.0"
            )
            dialog.run()
            dialog.destroy()
        GLib.idle_add(show_dialog)
    
    def _on_quit_clicked(self, widget):
        """Handle quit menu item click."""
        print("Tray: Quit clicked - shutting down...")
        self._running = False
        
        # Call quit handler first
        if self.on_quit:
            try:
                self.on_quit()
            except Exception as e:
                print(f"Error in quit handler: {e}")
        
        # Force exit the process
        def force_quit():
            print("Forcing application exit...")
            Gtk.main_quit()
            os._exit(0)
        
        GLib.timeout_add(100, force_quit)
    
    def set_recording(self, is_recording: bool):
        """Update recording state."""
        self._is_recording = is_recording
        
        def update():
            if self._toggle_item:
                if is_recording:
                    self._toggle_item.set_label("⏹️ Stop Recording")
                else:
                    self._toggle_item.set_label("🎤 Start Recording")
            if self._indicator and HAS_APPINDICATOR:
                # Update icon for recording state
                icon = "audio-input-microphone" if not is_recording else "media-record"
                self._indicator.set_icon(icon)
        
        GLib.idle_add(update)
    
    def start(self):
        """Start the system tray."""
        if not HAS_APPINDICATOR:
            print("Warning: AppIndicator3 not available. Running without tray icon.")
            return
        
        self._running = True
        self._gtk_thread = threading.Thread(target=self._run_gtk, daemon=True)
        self._gtk_thread.start()
    
    def _run_gtk(self):
        """Run GTK main loop in background thread."""
        # Create indicator
        self._indicator = AppIndicator3.Indicator.new(
            "whisperlayer",
            "audio-input-microphone",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self._indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        
        # Create and set menu
        self._menu = self._create_menu()
        self._indicator.set_menu(self._menu)
        
        # Run GTK main loop
        Gtk.main()
    
    def stop(self):
        """Stop the system tray."""
        self._running = False
        GLib.idle_add(Gtk.main_quit)
    
    def show_notification(self, title: str, message: str):
        """Show a desktop notification."""
        try:
            import subprocess
            subprocess.run(
                ["notify-send", title, message, "--icon=audio-input-microphone"],
                capture_output=True,
                timeout=5
            )
        except Exception:
            pass
