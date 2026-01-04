"""Modern PyQt5 Overlay - Gemini-style sliding bar with voice-reactive effects."""

import sys
import math
import threading
import time
from typing import Optional

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, QPoint, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath, QFont, QCursor

from . import config


class OverlaySignals(QObject):
    """Signals for thread-safe overlay updates."""
    show_signal = pyqtSignal()
    hide_signal = pyqtSignal()
    set_recording = pyqtSignal(bool)
    set_audio_level = pyqtSignal(float)
    set_window_name = pyqtSignal(str)
    set_transcription = pyqtSignal(str)
    set_status = pyqtSignal(str)
    cancel_signal = pyqtSignal()  # Emitted when user clicks cancel button


class GeminiOverlay(QWidget):
    """
    Gemini-style sliding overlay bar with voice-reactive effects.
    Slides from top, reacts to voice with flowing gradient.
    """
    
    def __init__(self):
        super().__init__()
        
        # Window Setup - Prevent focus stealing while remaining visible
        # Note: BypassWindowManagerHint can cause overlay to not appear on some systems
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.ToolTip |  # ToolTip windows typically don't steal focus
            Qt.WindowType.WindowDoesNotAcceptFocus  # Don't accept keyboard focus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)  # Critical for not stealing focus
        self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus, True)  # X11/XWayland hint
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # State Variables
        self._audio_level = 0.0
        self._target_audio_level = 0.0
        self._gradient_offset = 0.0
        self._is_recording = False
        self._window_name = ""
        self._status_text = "Ready"
        self._transcription_text = ""
        
        # Audio wave history for visualization (stores last N levels)
        self._audio_history = [0.0] * 40  # 40 samples for wave effect
        
        # Default screen geometry (will be updated on slide_in)
        self._update_screen_geometry()

        # Slide Animation
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.anim.setDuration(600)

        # Animation timer (shimmer + audio smoothing)
        self.shimmer_timer = QTimer()
        self.shimmer_timer.timeout.connect(self._update_animation)
        self.shimmer_timer.start(33)  # ~30 FPS
    
    def _update_screen_geometry(self):
        """Update geometry based on current cursor screen (multi-monitor support)."""
        # Get global cursor position
        cursor_pos = QCursor.pos()
        
        # Find screen containing cursor
        screen = QApplication.screenAt(cursor_pos)
        if screen is None:
            screen = QApplication.primaryScreen()
        
        # Use availableGeometry to respect panels/taskbars
        screen_geo = screen.availableGeometry()
        
        # Debug output
        print(f"Screen: {screen.name()}, Geometry: {screen_geo.x()},{screen_geo.y()} {screen_geo.width()}x{screen_geo.height()}")
        
        self.screen_x = screen_geo.x()
        self.screen_y = screen_geo.y()
        self.screen_width = screen_geo.width()
        self.screen_height = screen_geo.height()
        
        # Bar should be 92% of screen width - NO CAP, scales with screen
        self.bar_width = int(self.screen_width * 0.92)
        self.bar_height = 56
        
        # Center on THIS screen
        self.screen_center_x = self.screen_x + (self.screen_width - self.bar_width) // 2
        
        # Positions relative to THIS screen
        self.hidden_y = self.screen_y - self.bar_height - 20
        self.visible_y = self.screen_y + 15
        
        print(f"Overlay: x={self.screen_center_x}, width={self.bar_width}")
        
        self.setGeometry(self.screen_center_x, self.hidden_y, self.bar_width, self.bar_height)
        self.setFixedSize(self.bar_width, self.bar_height)
        self.resize(self.bar_width, self.bar_height)

    def slide_in(self):
        """Slide the overlay in from the top."""
        # Update screen geometry for current cursor position (multi-monitor)
        self._update_screen_geometry()
        
        self.anim.stop()
        
        # Disconnect any previous finished handlers
        try:
            self.anim.finished.disconnect()
        except:
            pass
        
        self.anim.setStartValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.start()
        self.show()
        
        # Just raise, don't activate (would steal focus)
        self.raise_()

    def slide_out(self):
        """Slide the overlay out to the top, then hide."""
        self.anim.stop()
        
        # Disconnect any previous finished handlers
        try:
            self.anim.finished.disconnect()
        except:
            pass
        
        # Hide window when animation finishes
        self.anim.finished.connect(self._on_slide_out_finished)
        
        self.anim.setStartValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.start()
    
    def _on_slide_out_finished(self):
        """Called when slide out animation completes - actually hide the window."""
        self.hide()

    def set_audio_data(self, level: float):
        """Set target audio level (0.0 to 1.0)."""
        self._target_audio_level = max(0.0, min(1.0, level))
        
        # Update audio history for wave visualization
        self._audio_history.pop(0)
        self._audio_history.append(self._target_audio_level)

    def set_recording(self, is_recording: bool):
        """Set recording state."""
        self._is_recording = is_recording
        if not is_recording:
            self._target_audio_level = 0.0
            # Clear audio history when stopping
            self._audio_history = [0.0] * len(self._audio_history)
        self.update()

    def set_window_name(self, name: str):
        """Set target window name."""
        self._window_name = name
        self.update()

    def set_transcription(self, text: str):
        """Set transcription text."""
        self._transcription_text = text
        self.update()

    def set_status(self, status: str):
        """Set status text."""
        self._status_text = status
        self.update()

    def _update_animation(self):
        """Update animation state."""
        # Smooth audio level transition
        self._audio_level += (self._target_audio_level - self._audio_level) * 0.25
        
        # Flowing gradient
        self._gradient_offset += 0.015
        if self._gradient_offset > 1:
            self._gradient_offset = 0
        
        self.update()

    def paintEvent(self, event):
        """Draw the overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 16  # Fixed rounded corners
        
        # Create rounded rect path
        path = QPainterPath()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), radius, radius)

        # --- Dynamic Gradient Background ---
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        
        base_alpha = 240
        boost = int(self._audio_level * 15)

        if self._is_recording:
            # Gemini-like colors: Blue -> Purple -> Pink
            c1 = QColor(40, 100, 240, base_alpha + boost)   # Blue
            c2 = QColor(140, 70, 240, base_alpha + boost)   # Purple
            c3 = QColor(240, 100, 180, base_alpha + boost)  # Pink
            
            # Flow effect with proper bounds
            gradient.setColorAt(0.0, c1)
            gradient.setColorAt(0.35, c2)
            gradient.setColorAt(0.7, c3)
            gradient.setColorAt(1.0, c1)
        else:
            # Idle: dark subtle gradient (Glassmorphism style)
            gradient.setColorAt(0, QColor(30, 32, 40, 240))
            gradient.setColorAt(1, QColor(40, 42, 50, 240))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # --- Border glow ---
        if self._is_recording:
            glow_alpha = int(80 + self._audio_level * 100)
            painter.setPen(QPen(QColor(120, 200, 255, glow_alpha), 2))
        else:
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # (Wave visualization removed for cleaner look)

        # --- Recording indicator dot (Left side) ---
        indicator_x = 32
        indicator_y = rect.height() // 2
        indicator_radius = 6
        
        if self._is_recording:
            pulse = 0.7 + 0.3 * math.sin(self._gradient_offset * math.pi * 6)
            painter.setBrush(QColor(255, 80, 80, int(255 * pulse)))  # Red for recording
        else:
            painter.setBrush(QColor(120, 120, 130))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(indicator_x, indicator_y), indicator_radius, indicator_radius)

        # --- Text (Spotify-style: show newest words, truncate from start) ---
        text = self._transcription_text if self._transcription_text else self._status_text
        
        # Dynamic max chars based on bar width (~12 pixels per character)
        # Bigger screens show more text automatically
        usable_width = self.bar_width - 150  # Leave space for indicator and close button
        max_chars = max(30, usable_width // 12)
        
        # Truncate from START to show newest words (tail)
        if len(text) > max_chars:
            text = "..." + text[-(max_chars - 3):]

        font = QFont("Segoe UI", 16)
        if not font.exactMatch():
            font = QFont("Inter", 16)
        if not font.exactMatch():
            font = QFont("Sans Serif", 16)
            
        font.setBold(True)
        painter.setFont(font)
        
        # Center the text
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(text)
        text_x = (rect.width() - text_width) // 2
        text_y = (rect.height() + fm.ascent() - fm.descent()) // 2

        # Shadow
        painter.setPen(QColor(0, 0, 0, 60))
        painter.drawText(text_x + 1, text_y + 2, text)
        
        # Main text - bright white
        painter.setPen(QColor(255, 255, 255, 255))
        painter.drawText(text_x, text_y, text)

        # --- Window name (right side) ---
        if self._window_name:
            small_font = QFont("Sans", 9)
            painter.setFont(small_font)
            
            window_text = f"→ {self._window_name}"
            if len(window_text) > 25:
                window_text = window_text[:22] + "..."
            
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(window_text)
            window_x = rect.width() - text_width - 60  # Leave room for cancel button
            
            painter.setPen(QColor(160, 160, 180, 160))
            painter.drawText(window_x, text_y, window_text)

        # --- Cancel/Close button (right side - always visible) ---
        self._cancel_btn_x = rect.width() - 44
        self._cancel_btn_y = rect.height() // 2
        self._cancel_btn_radius = 16
        
        # Button background - brighter when recording
        if self._is_recording:
            painter.setBrush(QColor(220, 80, 80, 200))  # Red when recording
        else:
            painter.setBrush(QColor(100, 100, 110, 180))  # Grey when idle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(
            QPoint(self._cancel_btn_x, self._cancel_btn_y), 
            self._cancel_btn_radius, 
            self._cancel_btn_radius
        )
        
        # X icon
        painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        offset = 6
        painter.drawLine(
            self._cancel_btn_x - offset, self._cancel_btn_y - offset,
            self._cancel_btn_x + offset, self._cancel_btn_y + offset
        )
        painter.drawLine(
            self._cancel_btn_x + offset, self._cancel_btn_y - offset,
            self._cancel_btn_x - offset, self._cancel_btn_y + offset
        )

    # Signal for cancel button click
    cancel_clicked = pyqtSignal()
    
    def mousePressEvent(self, event):
        """Handle mouse clicks - detect cancel button press."""
        if hasattr(self, '_cancel_btn_x'):
            # Check if click is within cancel button
            dx = event.pos().x() - self._cancel_btn_x
            dy = event.pos().y() - self._cancel_btn_y
            distance = (dx * dx + dy * dy) ** 0.5
            
            if distance <= self._cancel_btn_radius + 5:  # Small margin for easier clicking
                print("Cancel button clicked!")
                self.cancel_clicked.emit()
                return
        
        super().mousePressEvent(event)


class OverlayController:
    """Controller for managing the PyQt5 overlay from other threads."""
    
    def __init__(self, on_cancel=None):
        self._app: Optional[QApplication] = None
        self._window: Optional[GeminiOverlay] = None
        self._signals: Optional[OverlaySignals] = None
        self._qt_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._ready_event = threading.Event()
        self._on_cancel = on_cancel  # Callback for cancel button
    
    def start(self):
        """Start the Qt event loop in a separate thread."""
        if self._is_running:
            return
            
        self._is_running = True
        self._qt_thread = threading.Thread(target=self._run_qt, daemon=True)
        self._qt_thread.start()
        
        # Wait for Qt to be ready
        self._ready_event.wait(timeout=5.0)
    
    def _run_qt(self):
        """Run Qt event loop."""
        # Check if QApplication already exists
        self._app = QApplication.instance()
        if self._app is None:
            self._app = QApplication([])
        
        self._window = GeminiOverlay()
        self._signals = OverlaySignals()
        
        # Connect signals
        self._signals.show_signal.connect(self._window.slide_in)
        self._signals.hide_signal.connect(self._window.slide_out)
        self._signals.set_recording.connect(self._window.set_recording)
        self._signals.set_audio_level.connect(self._window.set_audio_data)
        self._signals.set_window_name.connect(self._window.set_window_name)
        self._signals.set_transcription.connect(self._window.set_transcription)
        self._signals.set_status.connect(self._window.set_status)
        
        # Connect cancel button
        if self._on_cancel:
            self._window.cancel_clicked.connect(self._on_cancel)
        
        self._ready_event.set()
        self._app.exec()
    
    def stop(self):
        """Stop the Qt event loop."""
        if self._app:
            self._app.quit()
        self._is_running = False
    
    def show(self):
        """Show overlay with slide animation."""
        if self._signals:
            self._signals.show_signal.emit()
    
    def hide(self):
        """Hide overlay with slide animation."""
        if self._signals:
            self._signals.hide_signal.emit()
    
    def set_recording(self, is_recording: bool):
        """Update recording state."""
        if self._signals:
            self._signals.set_recording.emit(is_recording)
    
    def set_audio_level(self, level: float):
        """Update audio level (0.0 to 1.0)."""
        if self._signals:
            self._signals.set_audio_level.emit(level)
    
    def set_window_name(self, name: str):
        """Update target window name."""
        if self._signals:
            self._signals.set_window_name.emit(name)
    
    def set_transcription(self, text: str):
        """Update transcription text."""
        if self._signals:
            self._signals.set_transcription.emit(text)
    
    def set_status(self, status: str):
        """Update status text."""
        if self._signals:
            self._signals.set_status.emit(status)
