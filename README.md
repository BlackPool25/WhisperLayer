# VoiceType 🎤

**Linux Native Speech-to-Text Voice Typing**

Transform your voice into text anywhere on your Linux desktop. Press a hotkey, speak, and your words appear where your cursor is.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-green)
![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange)

## ✨ Features

- **🎯 Type Anywhere** - Works in any application (browsers, editors, terminals)
- **🧠 Whisper AI** - OpenAI's state-of-the-art speech recognition
- **⚡ GPU Accelerated** - NVIDIA (CUDA) and AMD (ROCm) GPU support
- **🔒 Privacy First** - 100% offline, no cloud services
- **⌨️ Global Hotkey** - Configurable keyboard shortcut
- **🎚️ Live Streaming** - Real-time transcription as you speak
- **🖥️ Multi-Monitor** - Scales correctly on multi-monitor setups
- **🔧 System Tray** - Minimal, unobtrusive interface

## 📦 Installation

### Quick Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-username/voicetype.git
cd voicetype

# Run the installer
chmod +x install.sh
./install.sh
```

The installer will:
- Create a Python virtual environment
- Install all dependencies
- Add you to the `input` group (for global hotkeys)
- Create a desktop launcher
- Set up systemd service for auto-start

### Manual Installation

```bash
# Prerequisites (Ubuntu/Debian)
sudo apt install python3-venv python3-pip python3-gi portaudio19-dev

# For NVIDIA GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For AMD GPU support (ROCm)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.6

# Clone and install
git clone https://github.com/your-username/voicetype.git
cd voicetype
pip install -e .
```

## 🚀 Usage

### Starting VoiceType

**From Applications Menu:**
Search for "VoiceType" in your applications menu.

**From Terminal:**
```bash
voicetype
```

**As a Service:**
```bash
systemctl --user start voicetype
```

### Using Voice Typing

1. **Click** in any text field where you want to type
2. **Press** the hotkey (default: `Ctrl+Alt+F`)
3. **Speak** - your words are transcribed in real-time
4. **Stop speaking** - after 1.5s silence, text is typed automatically

The tray icon indicates recording status:
- 🔴 Red = Recording
- ⚫ Grey = Idle

### Settings

Right-click the tray icon → **Settings** to configure:

| Setting | Description |
|---------|-------------|
| **Model** | Whisper model size (tiny/base/small/medium/large/turbo) |
| **Device** | GPU acceleration (auto/cuda/cpu) |
| **Hotkey** | Custom keyboard shortcut |
| **Silence Duration** | Auto-stop timeout |
| **Input Device** | Microphone selection |
| **Auto-start** | Launch on login |

## 🎯 Whisper Models

| Model | VRAM | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| `tiny` | ~1GB | ⚡⚡⚡⚡ | ⭐ | Quick notes, low-end hardware |
| `base` | ~1GB | ⚡⚡⚡ | ⭐⭐ | General use |
| `small` | ~2GB | ⚡⚡ | ⭐⭐⭐ | Good balance |
| `medium` | ~5GB | ⚡ | ⭐⭐⭐⭐ | Better accuracy |
| `large` | ~10GB | 🐢 | ⭐⭐⭐⭐⭐ | Best accuracy |
| **`turbo`** | ~6GB | ⚡⚡⚡ | ⭐⭐⭐⭐ | **Recommended** |

## 🔧 Troubleshooting

### Hotkey Not Working

Ensure you're in the `input` group:
```bash
groups | grep input
# If not present:
sudo usermod -aG input $USER
# Log out and back in
```

### No GPU Acceleration

Check CUDA/ROCm is working:
```bash
python3 -c "import torch; print(torch.cuda.is_available())"
```

### Audio Issues

List available microphones:
```bash
python3 -c "import sounddevice; print(sounddevice.query_devices())"
```

### Wayland Compatibility

VoiceType works on Wayland but requires `ydotool` for text injection:
```bash
sudo apt install ydotool
```

## 📋 Requirements

- **OS:** Linux (Ubuntu 22.04+, Fedora 38+, Arch)
- **Python:** 3.10 or newer
- **GPU (optional):** NVIDIA with CUDA 11.8+ or AMD with ROCm 5.6+
- **RAM:** 4GB minimum, 8GB+ recommended
- **Microphone:** Any input device

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition model
- [PyTorch](https://pytorch.org/) - Deep learning framework
- [GTK](https://www.gtk.org/) - Settings UI framework

---

**Made with ❤️ for the Linux community**
