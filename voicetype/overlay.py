"""GTK3 Overlay window for displaying transcription status."""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GLib, Pango
import cairo
import threading
from typing import Optional

from . import config


class OverlayWindow(Gtk.Window):
    """
    Semi-transparent overlay window for displaying STT status.
    Designed with Antigravity-style aesthetics.
    """
    
    def __init__(self):
        super().__init__(title="VoiceType")
        
        # Window configuration
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        
        # Size and position
        self.set_default_size(config.OVERLAY_WIDTH, config.OVERLAY_HEIGHT)
        self._position_window()
        
        # Enable transparency
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        
        # State
        self._is_recording = False
        self._window_name = ""
        self._transcription_text = ""
        self._status_text = "Ready"
        
        # Create layout
        self._setup_ui()
        
        # Connect draw signal for custom rendering
        self.connect("draw", self._on_draw)
        
    def _position_window(self):
        """Position window at top-center of screen."""
        screen = self.get_screen()
        monitor = screen.get_primary_monitor()
        geometry = screen.get_monitor_geometry(monitor)
        
        x = geometry.x + (geometry.width - config.OVERLAY_WIDTH) // 2
        y = geometry.y + 50  # 50px from top
        
        self.move(x, y)
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Main container
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.main_box.set_margin_start(config.OVERLAY_PADDING)
        self.main_box.set_margin_end(config.OVERLAY_PADDING)
        self.main_box.set_margin_top(config.OVERLAY_PADDING)
        self.main_box.set_margin_bottom(config.OVERLAY_PADDING)
        self.add(self.main_box)
        
        # Top row: Status indicator + Window name
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.main_box.pack_start(top_box, False, False, 0)
        
        # Recording indicator (will be drawn with Cairo)
        self.indicator_area = Gtk.DrawingArea()
        self.indicator_area.set_size_request(12, 12)
        self.indicator_area.connect("draw", self._draw_indicator)
        top_box.pack_start(self.indicator_area, False, False, 0)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_markup(self._format_status())
        self.status_label.set_halign(Gtk.Align.START)
        top_box.pack_start(self.status_label, False, False, 0)
        
        # Window name (right-aligned)
        self.window_label = Gtk.Label()
        self.window_label.set_markup(self._format_window_name())
        self.window_label.set_halign(Gtk.Align.END)
        self.window_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.window_label.set_max_width_chars(30)
        top_box.pack_end(self.window_label, False, False, 0)
        
        # Separator line
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_box.pack_start(separator, False, False, 4)
        
        # Transcription text
        self.text_label = Gtk.Label()
        self.text_label.set_markup(self._format_transcription())
        self.text_label.set_halign(Gtk.Align.START)
        self.text_label.set_valign(Gtk.Align.START)
        self.text_label.set_line_wrap(True)
        self.text_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.text_label.set_max_width_chars(50)
        self.text_label.set_lines(2)
        self.text_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.main_box.pack_start(self.text_label, True, True, 0)
    
    def _on_draw(self, widget, cr):
        """Draw the window background with rounded corners."""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        radius = config.OVERLAY_CORNER_RADIUS
        
        # Draw rounded rectangle background
        self._draw_rounded_rect(cr, 0, 0, width, height, radius)
        
        # Fill with background color
        cr.set_source_rgba(*config.OVERLAY_BG_COLOR)
        cr.fill()
        
        # Propagate draw to children
        return False
    
    def _draw_rounded_rect(self, cr, x, y, width, height, radius):
        """Draw a rounded rectangle path."""
        degrees = 3.14159 / 180.0
        
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -90 * degrees, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, 90 * degrees)
        cr.arc(x + radius, y + height - radius, radius, 90 * degrees, 180 * degrees)
        cr.arc(x + radius, y + radius, radius, 180 * degrees, 270 * degrees)
        cr.close_path()
    
    def _draw_indicator(self, widget, cr):
        """Draw the recording indicator circle."""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        radius = min(width, height) / 2 - 1
        
        cr.arc(width / 2, height / 2, radius, 0, 2 * 3.14159)
        
        if self._is_recording:
            # Pulsing green for recording
            cr.set_source_rgba(*config.OVERLAY_ACCENT_COLOR)
        else:
            # Gray when not recording
            cr.set_source_rgba(0.4, 0.4, 0.4, 1.0)
        
        cr.fill()
        return True
    
    def _format_status(self) -> str:
        """Format status text with markup."""
        color = "white" if self._is_recording else "gray"
        return f'<span foreground="{color}" font_desc="10">{self._status_text}</span>'
    
    def _format_window_name(self) -> str:
        """Format window name with markup."""
        name = self._window_name or "No window"
        return f'<span foreground="#999999" font_desc="9">→ {GLib.markup_escape_text(name)}</span>'
    
    def _format_transcription(self) -> str:
        """Format transcription text with markup."""
        text = self._transcription_text or "Listening..."
        return f'<span foreground="white" font_desc="12">{GLib.markup_escape_text(text)}</span>'
    
    def set_recording(self, is_recording: bool):
        """Update recording state."""
        self._is_recording = is_recording
        self._status_text = "Recording..." if is_recording else "Ready"
        self._update_ui()
    
    def set_window_name(self, name: str):
        """Update the target window name."""
        self._window_name = name
        self._update_ui()
    
    def set_transcription(self, text: str):
        """Update the transcription text."""
        self._transcription_text = text
        self._update_ui()
    
    def set_status(self, status: str):
        """Update the status text."""
        self._status_text = status
        self._update_ui()
    
    def _update_ui(self):
        """Update all UI elements (thread-safe)."""
        def update():
            self.status_label.set_markup(self._format_status())
            self.window_label.set_markup(self._format_window_name())
            self.text_label.set_markup(self._format_transcription())
            self.indicator_area.queue_draw()
            self.queue_draw()
            return False
        
        GLib.idle_add(update)
    
    def show_overlay(self):
        """Show the overlay window (thread-safe)."""
        def show():
            self.show_all()
            return False
        GLib.idle_add(show)
    
    def hide_overlay(self):
        """Hide the overlay window (thread-safe)."""
        def hide():
            self.hide()
            return False
        GLib.idle_add(hide)


class OverlayController:
    """Controller for managing the overlay in a separate thread."""
    
    def __init__(self):
        self._window: Optional[OverlayWindow] = None
        self._gtk_thread: Optional[threading.Thread] = None
        self._main_loop: Optional[GLib.MainLoop] = None
        self._is_running = False
    
    def start(self):
        """Start the GTK main loop in a separate thread."""
        if self._is_running:
            return
            
        self._is_running = True
        self._gtk_thread = threading.Thread(target=self._run_gtk, daemon=True)
        self._gtk_thread.start()
        
        # Wait for window to be created
        import time
        for _ in range(50):  # 5 second timeout
            if self._window is not None:
                break
            time.sleep(0.1)
    
    def _run_gtk(self):
        """Run GTK main loop."""
        # Initialize GTK
        Gtk.init([])
        
        # Create window
        self._window = OverlayWindow()
        
        # Create main loop
        self._main_loop = GLib.MainLoop()
        
        # Run
        self._main_loop.run()
    
    def stop(self):
        """Stop the GTK main loop."""
        if self._main_loop:
            GLib.idle_add(self._main_loop.quit)
        self._is_running = False
    
    @property
    def window(self) -> Optional[OverlayWindow]:
        """Get the overlay window."""
        return self._window
    
    def show(self):
        """Show the overlay."""
        if self._window:
            self._window.show_overlay()
    
    def hide(self):
        """Hide the overlay."""
        if self._window:
            self._window.hide_overlay()
    
    def set_recording(self, is_recording: bool):
        """Update recording state."""
        if self._window:
            self._window.set_recording(is_recording)
    
    def set_window_name(self, name: str):
        """Update target window name."""
        if self._window:
            self._window.set_window_name(name)
    
    def set_transcription(self, text: str):
        """Update transcription text."""
        if self._window:
            self._window.set_transcription(text)
    
    def set_status(self, status: str):
        """Update status text."""
        if self._window:
            self._window.set_status(status)
