# VoiceType - Linux Native STT Voice Typing

A modern Linux native speech-to-text application that enables voice typing into any active window with a hotkey-triggered overlay.

## ✨ Features

- 🎤 **Live Transcription** - Real-time speech-to-text using OpenAI Whisper
- ⌨️ **Auto-Type** - Automatically types transcribed text into the active window
- 🎨 **Modern Overlay** - Sleek Gemini-style sliding bar with voice-reactive color effects
- 🔧 **Modern Settings** - Beautiful dark-themed settings with live configuration updates
- 🔥 **GPU Accelerated** - Supports CUDA (NVIDIA) and ROCm (AMD)
- 🐧 **Linux Native** - Works on X11 and Wayland (GNOME, KDE, etc.)
- 🔊 **Smart Audio** - Shows friendly device names like Ubuntu Sound Settings
- ⚡ **Hot Reload** - Change settings without restarting the app

## 📋 Requirements

- Python 3.10+
- Linux with X11 or Wayland
- GPU recommended (NVIDIA CUDA or AMD ROCm) for faster transcription
- PulseAudio or PipeWire for audio

## 🚀 Quick Installation

```bash
# Clone and install
git clone https://github.com/yourusername/voicetype.git
cd voicetype
./install.sh
```

The installer will:
- Install system dependencies
- Set up a Python virtual environment
- Configure ydotool for text injection
- Add desktop integration

## 📦 Manual Installation

```bash
# System dependencies (Debian/Ubuntu)
sudo apt install python3-dev python3-venv python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-appindicator3-0.1 \
    portaudio19-dev libpulse-dev \
    ydotool xdotool

# Add user to input group (for global hotkeys)
sudo usermod -aG input $USER
# Log out and back in for group changes

# Python environment
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

## 🎯 Usage

```bash
# Run VoiceType
voicetype

# Or with virtual environment
source .venv/bin/activate
python -m voicetype
```

**Default Hotkey**: `Ctrl+Alt+F` - Press to start/stop recording

## ⚙️ Configuration

Access settings via the system tray icon or run with `--settings`.

### Available Settings:

| Setting | Description |
|---------|-------------|
| **Whisper Model** | tiny, base, small, medium, large, turbo |
| **Compute Device** | auto, cpu, cuda |
| **Microphone** | Select from detected audio devices |
| **Hotkey** | Custom keyboard shortcut |
| **Silence Timeout** | Auto-stop after silence (0.5-5 seconds) |
| **Auto-start** | Launch on login |

### Model Recommendations:

| Model | VRAM | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| tiny | ~1GB | ⚡⚡⚡⚡ | ★☆☆☆ | Quick drafts |
| base | ~1GB | ⚡⚡⚡ | ★★☆☆ | General use |
| small | ~2GB | ⚡⚡ | ★★★☆ | Good balance |
| medium | ~5GB | ⚡ | ★★★★ | High accuracy |
| **turbo** | ~6GB | ⚡⚡⚡ | ★★★★ | **Recommended** |
| large | ~10GB | ⚡ | ★★★★★ | Best accuracy |

## 🖼️ Screenshots

### Voice-Reactive Overlay
The overlay slides from the top and reacts to your voice with animated color effects.

### Modern Settings
Dark-themed settings with grouped options and real-time device detection.

## 🔧 Troubleshooting

### Hotkey not working?
- Ensure you're in the `input` group: `groups | grep input`
- On Wayland, evdev is used for global hotkeys (requires input group)

### No audio devices showing?
- Make sure PulseAudio/PipeWire is running
- Install pulsectl: `pip install pulsectl`

### Text not typing?
- Check ydotool service: `systemctl status ydotoold`
- Make sure you're in the `input` group

### GPU not detected?
- For NVIDIA: Install CUDA and pytorch with CUDA support
- For AMD: Install ROCm and pytorch with ROCm support

## 📁 Project Structure

```
voicetype/
├── __main__.py     # Entry point
├── app.py          # Main application controller
├── audio.py        # Audio capture with sounddevice
├── config.py       # Configuration and settings bridge
├── hotkey.py       # Global hotkey handling (evdev/pynput)
├── overlay.py      # Modern animated overlay
├── settings.py     # Settings persistence and management
├── settings_ui.py  # Modern GTK3 settings window
├── system.py       # Text injection and window detection
├── transcriber.py  # Whisper transcription
└── tray.py         # System tray integration
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see LICENSE file for details.
