# VoiceType - Linux Native STT Voice Typing

A lightweight Linux native speech-to-text application that enables voice typing into any active window with a hotkey-triggered overlay.

## Features

- 🎤 **Live Transcription** - Real-time speech-to-text using faster-whisper with GPU acceleration
- ⌨️ **Auto-Type** - Automatically types transcribed text into the active window
- 🖥️ **Overlay Display** - Sleek, semi-transparent overlay showing transcription status
- 🔥 **GPU Accelerated** - Optimized for AMD ROCm (tested on RX 7900 GRE)
- 🐧 **Linux Native** - Works on X11 and Wayland

## Requirements

- Python 3.10+
- AMD GPU with ROCm 6.0+ (or NVIDIA with CUDA)
- System packages: `ydotool`, `xdotool`, GTK3

## Installation

```bash
# System dependencies
sudo apt install ydotool xdotool python3-gi python3-gi-cairo gir1.2-gtk-3.0 libportaudio2

# Enable ydotool daemon
sudo systemctl enable --now ydotoold

# Python environment (--system-site-packages needed for PyGObject)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source .venv/bin/activate
python -m voicetype
```

**Default Hotkey**: `Ctrl+Shift+S` - Press to start/stop recording

## Configuration

Edit `config.py` to customize:
- Hotkey binding
- Whisper model size
- Overlay appearance
- Audio settings
