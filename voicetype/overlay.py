"""Modern PyQt5 Overlay - Gemini-style sliding bar with voice-reactive effects."""

import sys
import math
import threading
import time
from typing import Optional

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, QPoint, pyqtSignal, QObject
from PyQt5.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath, QFont

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


class GeminiOverlay(QWidget):
    """
    Gemini-style sliding overlay bar with voice-reactive effects.
    Slides from top, reacts to voice with flowing gradient.
    """
    
    def __init__(self):
        super().__init__()
        
        # Window Setup (Frameless, Transparent, Always on Top)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool  # Hides from taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # State Variables
        self._audio_level = 0.0
        self._target_audio_level = 0.0
        self._gradient_offset = 0.0
        self._is_recording = False
        self._window_name = ""
        self._status_text = "Ready"
        self._transcription_text = ""
        
        # Screen Scaling & Geometry
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.bar_width = int(self.screen_width * 0.9)  # 90% of screen width
        self.bar_height = 56
        self.screen_center_x = (self.screen_width - self.bar_width) // 2
        
        # Positions
        self.hidden_y = -self.bar_height - 20
        self.visible_y = 25  # Margin from top
        
        self.setGeometry(self.screen_center_x, self.hidden_y, self.bar_width, self.bar_height)

        # Slide Animation
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setDuration(500)

        # Animation timer (shimmer + audio smoothing)
        self.shimmer_timer = QTimer()
        self.shimmer_timer.timeout.connect(self._update_animation)
        self.shimmer_timer.start(33)  # ~30 FPS

    def slide_in(self):
        """Slide the overlay in from the top."""
        self.anim.stop()
        self.anim.setStartValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.start()
        self.show()

    def slide_out(self):
        """Slide the overlay out to the top."""
        self.anim.stop()
        self.anim.setStartValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.start()

    def set_audio_data(self, level: float):
        """Set target audio level (0.0 to 1.0)."""
        self._target_audio_level = max(0.0, min(1.0, level))

    def set_recording(self, is_recording: bool):
        """Set recording state."""
        self._is_recording = is_recording
        if not is_recording:
            self._target_audio_level = 0.0
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
        radius = rect.height() // 2
        
        # Create rounded rect path
        path = QPainterPath()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), radius, radius)

        # --- Dynamic Gradient Background ---
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        
        base_alpha = 235
        boost = int(self._audio_level * 20)

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
            # Idle: dark subtle gradient
            gradient.setColorAt(0, QColor(30, 30, 40, base_alpha))
            gradient.setColorAt(1, QColor(40, 35, 50, base_alpha))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # --- Border glow ---
        if self._is_recording:
            glow_alpha = int(80 + self._audio_level * 120)
            painter.setPen(QPen(QColor(100, 180, 255, glow_alpha), 2))
        else:
            painter.setPen(QPen(QColor(80, 80, 100, 60), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # --- Audio Reaction Glow (inner) ---
        if self._is_recording and self._audio_level > 0.02:
            center_x = rect.width() / 2
            center_y = rect.height() / 2
            
            glow_width = rect.width() * 0.3 * self._audio_level
            glow_height = rect.height() * 0.5
            
            glow_rect = QRect(
                int(center_x - glow_width / 2),
                int(center_y - glow_height / 2),
                int(glow_width),
                int(glow_height)
            )
            
            glow_path = QPainterPath()
            glow_path.addRoundedRect(
                float(glow_rect.x()), float(glow_rect.y()),
                float(glow_rect.width()), float(glow_rect.height()),
                glow_height / 2, glow_height / 2
            )
            
            glow_color = QColor(255, 255, 255, int(80 * self._audio_level))
            painter.setBrush(QBrush(glow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(glow_path)

        # --- Recording indicator dot ---
        indicator_x = 24
        indicator_y = rect.height() // 2
        indicator_radius = 6
        
        if self._is_recording:
            pulse = 0.7 + 0.3 * math.sin(self._gradient_offset * math.pi * 6)
            painter.setBrush(QColor(50, 240, 120, int(255 * pulse)))
        else:
            painter.setBrush(QColor(120, 120, 130))
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(indicator_x, indicator_y), indicator_radius, indicator_radius)

        # --- Text ---
        text = self._transcription_text if self._transcription_text else self._status_text
        max_chars = 50
        if len(text) > max_chars:
            text = text[:max_chars - 3] + "..."

        font = QFont("Sans", 12)
        painter.setFont(font)
        
        text_x = 45
        text_y = rect.height() // 2 + 5

        # Shadow
        painter.setPen(QColor(0, 0, 0, 80))
        painter.drawText(text_x + 1, text_y + 1, text)
        
        # Main text
        painter.setPen(QColor(255, 255, 255, 240))
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
            window_x = rect.width() - text_width - 20
            
            painter.setPen(QColor(160, 160, 180, 160))
            painter.drawText(window_x, text_y, window_text)


class OverlayController:
    """Controller for managing the PyQt5 overlay from other threads."""
    
    def __init__(self):
        self._app: Optional[QApplication] = None
        self._window: Optional[GeminiOverlay] = None
        self._signals: Optional[OverlaySignals] = None
        self._qt_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._ready_event = threading.Event()
    
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
