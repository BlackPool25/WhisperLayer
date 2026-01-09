# WhisperLayer 🎤

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
- **📝 Formatted AI** - Ollama responses keep lists, paragraphs, and code blocks
- **🚀 Turbo Typing** - Optimized text injection (8ms delay) with smart buffering

## 📦 Installation

### Auto-Install (All Distros)
WhisperLayer supports **Ubuntu/Debian**, **Fedora**, **Arch**, and **OpenSUSE**.

```bash
# Clone the repository
git clone https://github.com/your-username/whisperlayer.git
cd whisperlayer

# Run the installer
bash install.sh
```

The installer detects your distro and installs all dependencies automatically.

### Manual Installation
If you prefer to do it manually:

```bash
# 1. Install System Deps
# Ubuntu/Debian
sudo apt install python3-venv python3-pip python3-gi portaudio19-dev python3-pyqt5 ydotool

# Fedora
sudo dnf install python3 python3-pip python3-gobject portaudio-devel python3-qt5 ydotool

# Arch
sudo pacman -S python-virtualenv python-pip python-gobject portaudio python-pyqt5 ydotool

# For NVIDIA GPU support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For AMD GPU support (ROCm)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.6

# Clone and install
git clone https://github.com/your-username/whisperlayer.git
cd whisperlayer
pip install -e .
```

### Updating

```bash
# Run the updater to see available releases
./update.sh

# Or automatically install the latest
./update.sh --latest

# Just list releases without installing
./update.sh --list-only
```

### Uninstalling

```bash
# Interactive uninstall (prompts for each component)
./uninstall.sh

# Remove everything without prompts
./uninstall.sh --all

# Remove all except configuration (keep settings for reinstall)
./uninstall.sh --all --keep-config
```

## 🎤 Voice Commands Guide

Commands are triggered by saying **"Okay [Action]"**.

### 1. Instant Commands
These execute immediately. No end phrase needed.

| Command | Behavior | Description |
|---------|----------|-------------|
| `Okay copy` | Ctrl+C | Copy selected text |
| `Okay paste` | Ctrl+V | Paste clipboard (or substitute if nested) |
| `Okay cut` | Ctrl+X | Cut selected text |
| `Okay undo` | Ctrl+Z | Undo last action |
| `Okay redo` | Ctrl+Shift+Z | Redo action |
| `Okay select all` | Ctrl+A | Select all text |
| `Okay delete` | Ctrl+Backspace | Delete previous word |
| `Okay backspace` | Backspace | Delete previous character |
| `Okay new line` | Enter | Insert new line |
| `Okay enter` | Enter | Press Enter key |
| `Okay tab` | Tab | Press Tab key |
| `Okay super` | Super (Windows) | Open Activities/Start |
| `Okay lock` | Super+L | Lock Screen |
| `Okay command prompt` | Alt+F2 | Run Command Prompt |
| `Okay tab` | Alt+Tab | Switch Window (Quick) |
| `Okay new tab` | Ctrl+T | New Browser Tab |
| `Okay new window` | Ctrl+N | New Window |
| `Okay press tab` | Tab | Press Tab Key (Literal) |

### 2. Block Commands
These require content and an end phrase.

**Valid End Phrases:** `done`, `stop`, `end`, `finished`, `complete`, `over`, `execute`.

**Syntax:** `Okay [Command] [Content] Okay [End]`

| Command | Action | Example |
|---------|--------|---------|
| `Okay search` | Google Search | `Okay search what is linux okay done` |
| `Okay google` | Google Search | `Okay google weather today okay done` |
| `Okay delta` | Local AI Query | `Okay delta write a poem okay done` |
| `Okay wait` | Pause Execution | `Okay wait three seconds okay done` |
| `Okay raw text` | Type Verbatim | `Okay raw text ignore commands okay done` |

> **Note:** "Raw Text" mode ignores any command triggers inside it. Use this when dictating text that might contain words like "okay", "copy", etc.

### 3. Advanced Features

#### 🤖 Local AI Integration (@delta)
WhisperLayer integrates with **Ollama** to provide private, local AI assistance.
- **Command:** `Okay delta [Query] Okay done`
- **Effect:** Submits your query to a local LLM and types the response.
- **Formatting:** Preserves lists, code blocks, and paragraphs automatically.

**Setup:**
1. Install Ollama: `curl -fsSL https://ollama.com/install.sh | sh`
2. Pull a model (Gemma 2B recommended for speed): `ollama pull gemma:2b`
3. Start the server: `ollama serve` (or let it run in background)

#### 🔗 Nested Substitution (Search with Paste)
You can use `okay paste` *inside* other commands to use your clipboard content as input.

- **Workflow:** Copy text -> Say `Okay search okay paste okay done`.
- **Result:** Searches Google for the text currently in your clipboard.
- **Why?** The system detects `okay paste` inside the search command, fetches your clipboard text, and "pastes" it into the search query before executing.

#### ⛓️ Sequential Commands
You can chain multiple commands in one breath.
- **Example:** `Okay new line okay new line okay paste`
- **Result:** Inserts two new lines and then pastes text.

## 🚀 Usage

### Starting WhisperLayer

**From Applications Menu:**
Search for "WhisperLayer" in your applications menu.

**From Terminal:**
```bash
whisperlayer
```

**As a Service:**
```bash
systemctl --user start whisperlayer
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
| **Model** | Whisper model size (tiny...turbo) |
| **Device** | GPU acceleration (auto/cuda/cpu) |
| **Hotkey** | Custom keyboard shortcut |
| **Silence Duration** | Auto-stop timeout |
| **Input Device** | Microphone selection |
| **Auto-start** | Launch on login |

### Custom Commands
Create powerful voice macros with the **Rich Command Editor**:

1. Go to **Settings** -> **Custom Commands**
2. Click **Add Command**
3. Defines your **Trigger** (e.g. "explain code")
4. Use the **Macro Editor** to build your action

#### ✨ Macro Editor Features:
- **⌨️ Key Recording**: Click the keyboard icon to record real shortcuts (e.g. `<ctrl+c>`).
- **🤖 AI Actions**: Type `@` to select commands like `@delta`.
- **📦 Smart Queries**: Commands like `@delta` automatically add a query box for your prompt.
- **🔄 Mixed Mode**: Combine text, keys, and AI commands in one macro!
  - *Example:* `Copying selection <ctrl+c>... @delta[Explain this code: {content}]`

#### 🏷️ Command Types
- **⚡ Instant**: Executes immediately (Keys, simple text).
- **🛑 Block**: Requires an end phrase (e.g. "Okay done") to capture content.

#### 🔄 Renaming Built-in Commands
Don't like saying "Okay copy"? rename it!
- Go to **Settings** -> **System Commands**
- Click the text box next to any command (e.g., "copy")
- Type your new trigger (e.g., "duplicate")
- Now say "Okay duplicate" to copy!

#### 🏷️ Command Aliases (@)
You can create custom commands that reference or extend other commands.
- **Value:** Starts with `@` followed by the target command trigger.

**Examples:**
| Trigger | Value | Effect |
|---------|-------|--------|
| `Okay code` | `@delta[write code for {content}]` | Uses AI to write code based on what you say |
| `Okay dup` | `@copy` | "Okay dup" triggers "Okay copy" |
| `Okay explain` | `@delta[explain this code]` | Quick shortcut for AI explanation |

You can also **Disable Built-in Commands** in the "System Commands" section if they interfere with your dictation.

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

WhisperLayer works on Wayland but requires `ydotool` for text injection:
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
