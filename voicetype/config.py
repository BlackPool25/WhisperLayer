"""Configuration settings for VoiceType"""

# Hotkey configuration
HOTKEY = "<ctrl>+<alt>+f"

# Whisper model settings
# Using openai-whisper with PyTorch ROCm for AMD GPU support
# Available models: tiny, base, small, medium, large, turbo
WHISPER_MODEL = "turbo"  # Best balance of speed/accuracy on GPU
WHISPER_LANGUAGE = "en"

# Audio settings
SAMPLE_RATE = 16000
CHUNK_DURATION = 0.5  # seconds per chunk
BUFFER_DURATION = 5.0  # rolling buffer size in seconds
SILENCE_THRESHOLD = 0.01  # RMS threshold for silence detection
SILENCE_DURATION = 1.5  # seconds of silence before finalizing

# Overlay settings
OVERLAY_WIDTH = 500
OVERLAY_HEIGHT = 120
OVERLAY_OPACITY = 0.92
OVERLAY_PADDING = 20
OVERLAY_CORNER_RADIUS = 16

# Colors (RGBA)
OVERLAY_BG_COLOR = (0.1, 0.1, 0.12, 0.95)
OVERLAY_TEXT_COLOR = (1.0, 1.0, 1.0, 1.0)
OVERLAY_ACCENT_COLOR = (0.4, 0.8, 0.4, 1.0)  # Recording indicator
OVERLAY_MUTED_COLOR = (0.6, 0.6, 0.6, 1.0)  # Window name
