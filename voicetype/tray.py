"""System tray integration for VoiceType using GTK3 AppIndicator."""

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
    
    def _create_menu(self) -> Gtk.Menu:
        """Create the tray menu."""
        menu = Gtk.Menu()
        
        # Toggle recording
        self._toggle_item = Gtk.MenuItem(label="Start Recording")
        self._toggle_item.connect("activate", self._on_toggle_clicked)
        menu.append(self._toggle_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Settings
        settings_item = Gtk.MenuItem(label="Settings...")
        settings_item.connect("activate", self._on_settings_clicked)
        menu.append(settings_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # About
        about_item = Gtk.MenuItem(label="About")
        about_item.connect("activate", self._on_about_clicked)
        menu.append(about_item)
        
        # Quit
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self._on_quit_clicked)
        menu.append(quit_item)
        
        menu.show_all()
        return menu
    
    def _on_toggle_clicked(self, widget):
        """Handle toggle menu item click."""
        if self.on_toggle:
            self.on_toggle()
    
    def _on_settings_clicked(self, widget):
        """Handle settings menu item click."""
        if self.on_settings:
            self.on_settings()
    
    def _on_about_clicked(self, widget):
        """Show about dialog."""
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="VoiceType"
        )
        dialog.format_secondary_text(
            "Linux Native Speech-to-Text Voice Typing\n\n"
            "Press your hotkey to start/stop recording.\n"
            "Transcribed text will be typed automatically."
        )
        dialog.run()
        dialog.destroy()
    
    def _on_quit_clicked(self, widget):
        """Handle quit menu item click."""
        self._running = False
        if self.on_quit:
            self.on_quit()
        Gtk.main_quit()
    
    def set_recording(self, is_recording: bool):
        """Update recording state."""
        self._is_recording = is_recording
        
        def update():
            if self._toggle_item:
                self._toggle_item.set_label(
                    "Stop Recording" if is_recording else "Start Recording"
                )
            if self._indicator and HAS_APPINDICATOR:
                # Could update icon here for recording state
                pass
        
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
            "voicetype",
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
