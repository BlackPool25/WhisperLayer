import sys
import random
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, pyqtProperty, QPoint
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath

class GeminiOverlay(QWidget):
    def __init__(self):
        super().__init__()
        
        # 1. Window Setup (Frameless, Transparent, Always on Top)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool  # Tool hides it from the taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # 2. State Variables
        self.audio_level = 0.0  # Normalized 0.0 to 1.0
        self.gradient_offset = 0.0 # For animating the gradient flow
        
        # 3. Screen Scaling & Geometry
        screen = QApplication.primaryScreen().geometry()
        self.screen_width = screen.width()
        self.bar_width = int(self.screen_width * 0.40) # 40% of screen width
        self.bar_height = int(screen.height() * 0.08)  # 8% of screen height
        self.screen_center_x = (self.screen_width - self.bar_width) // 2
        
        # Start position (hidden above screen)
        self.hidden_y = -self.bar_height - 20
        self.visible_y = 40 # Margin from top
        
        self.setGeometry(self.screen_center_x, self.hidden_y, self.bar_width, self.bar_height)

        # 4. Animation Setup
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setDuration(600) # 600ms slide duration

        # 5. Internal Timer for "Living" Gradient (Makes it shimmer)
        self.shimmer_timer = QTimer()
        self.shimmer_timer.timeout.connect(self.update_shimmer)
        self.shimmer_timer.start(50)

    def slide_in(self):
        self.anim.setStartValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.start()
        self.show()

    def slide_out(self):
        self.anim.setStartValue(QPoint(self.screen_center_x, self.visible_y))
        self.anim.setEndValue(QPoint(self.screen_center_x, self.hidden_y))
        self.anim.start()

    def update_audio_data(self, level):
        """
        Call this method from your main app logic with the current sound level.
        :param level: float between 0.0 (silence) and 1.0 (max volume)
        """
        self.audio_level = level
        self.update() # Triggers paintEvent

    def update_shimmer(self):
        # Moves the gradient slightly to create a "living" AI feel
        self.gradient_offset += 0.02
        if self.gradient_offset > 1:
            self.gradient_offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Create Rounded Rect Path
        rect = self.rect()
        radius = rect.height() // 2
        path = QPainterPath()
        path.addRoundedRect(0, 0, rect.width(), rect.height(), radius, radius)

        # --- Dynamic Gemini Gradient ---
        # Colors: Deep Blue -> Purple -> Pink -> White
        gradient = QLinearGradient(0, 0, rect.width(), 0)
        
        # We shift stops based on gradient_offset to make it "flow"
        # We also boost intensity based on self.audio_level
        
        base_alpha = 220  # Slightly transparent background
        boost = int(self.audio_level * 35) # Brighten on loud sounds

        # Key Gemini-like colors
        c1 = QColor(40, 100, 240, base_alpha + boost)   # Blue
        c2 = QColor(140, 70, 240, base_alpha + boost)   # Purple
        c3 = QColor(240, 180, 200, base_alpha + boost)  # Pink
        
        # Simple flow effect
        stop1 = (0.0 + self.gradient_offset) % 1.0
        stop2 = (0.5 + self.gradient_offset) % 1.0
        stop3 = (1.0 + self.gradient_offset) % 1.0

        gradient.setColorAt(stop1, c1)
        gradient.setColorAt(stop2, c2)
        gradient.setColorAt(stop3, c3)

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # --- Audio Reaction Bar (Inner Glow) ---
        # Draws a white overlay that grows from the center based on volume
        if self.audio_level > 0.01:
            center_x = rect.width() / 2
            center_y = rect.height() / 2
            
            # Width reacts to audio
            glow_width = rect.width() * self.audio_level
            glow_height = rect.height() * (0.3 + (self.audio_level * 0.4)) # Gets thicker too
            
            glow_rect = QRect(0, 0, int(glow_width), int(glow_height))
            glow_rect.moveCenter(QPoint(int(center_x), int(center_y)))
            
            glow_path = QPainterPath()
            glow_path.addRoundedRect(
                float(glow_rect.x()), float(glow_rect.y()), 
                float(glow_rect.width()), float(glow_rect.height()), 
                10.0, 10.0
            )
            
            # White with varying opacity
            glow_color = QColor(255, 255, 255, int(100 * self.audio_level))
            painter.setBrush(QBrush(glow_color))
            painter.drawPath(glow_path)


# --- Simulation Wrapper for Testing ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = GeminiOverlay()
    
    # 1. Slide it in immediately
    QTimer.singleShot(500, window.slide_in)

    # 2. Simulate external sound data coming in
    # In your real app, you would delete this and call window.update_audio_data(val)
    sim_timer = QTimer()
    def simulate_audio():
        # Generate fake waveform data with some randomness
        import math
        import time
        t = time.time() * 5
        # Create a sine wave + noise pattern
        val = (math.sin(t) + 1) / 2  # 0 to 1 sine
        val = val * 0.6 + random.random() * 0.4 # Add noise
        window.update_audio_data(val)

    sim_timer.timeout.connect(simulate_audio)
    sim_timer.start(50) # Update every 50ms

    # 3. Auto slide out after 10 seconds (example)
    QTimer.singleShot(10000, window.slide_out)
    QTimer.singleShot(11000, app.quit)

    sys.exit(app.exec())