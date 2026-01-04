#!/usr/bin/env bash
# WhisperLayer Installation Script
# IMPORTANT: Run with 'bash install.sh' NOT 'sh install.sh'

set -e

# Ensure we're running with bash
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Error: This script requires bash. Please run with: bash install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/whisperlayer.desktop"
SERVICE_FILE="$HOME/.config/systemd/user/whisperlayer.service"
AUTOSTART_FILE="$HOME/.config/autostart/whisperlayer.desktop"

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   ${GREEN}WhisperLayer Installer v1.0.0-beta${NC}       ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}   Linux Native Speech-to-Text             ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Available Whisper models
declare -A MODELS
MODELS=(
    ["tiny"]="~1GB VRAM, fastest, basic accuracy"
    ["base"]="~1GB VRAM, fast, good accuracy"
    ["small"]="~2GB VRAM, balanced speed/accuracy"
    ["medium"]="~5GB VRAM, slower, great accuracy"
    ["large"]="~10GB VRAM, slowest, best accuracy"
    ["turbo"]="~6GB VRAM, fast + accurate (RECOMMENDED)"
)

select_model() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Select Whisper Model${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo ""
    echo "Available models (larger = more accurate but slower):"
    echo ""
    
    local i=1
    local model_array=("tiny" "base" "small" "medium" "large" "turbo")
    
    for model in "${model_array[@]}"; do
        if [ "$model" = "turbo" ]; then
            echo -e "  ${GREEN}$i) $model${NC} - ${MODELS[$model]} ${GREEN}★${NC}"
        else
            echo "  $i) $model - ${MODELS[$model]}"
        fi
        ((i++))
    done
    
    echo ""
    echo -e "  ${YELLOW}Note: You can change this later in Settings${NC}"
    echo ""
    
    local default=6  # turbo
    read -p "Select model [1-6, default=$default (turbo)]: " choice
    choice=${choice:-$default}
    
    case $choice in
        1) SELECTED_MODEL="tiny" ;;
        2) SELECTED_MODEL="base" ;;
        3) SELECTED_MODEL="small" ;;
        4) SELECTED_MODEL="medium" ;;
        5) SELECTED_MODEL="large" ;;
        6|*) SELECTED_MODEL="turbo" ;;
    esac
    
    echo ""
    print_success "Selected model: $SELECTED_MODEL"
}

print_header

# Detect package manager and install system dependencies
print_step "Checking system dependencies..."

if command -v apt-get &> /dev/null; then
    echo "  Detected: Debian/Ubuntu"
    print_step "Installing system packages (may require sudo password)..."
    sudo apt-get update -qq 2>/dev/null || true
    sudo apt-get install -y -qq \
        python3 python3-venv python3-pip python3-gi \
        portaudio19-dev libgirepository1.0-dev gir1.2-appindicator3-0.1 \
        python3-pyqt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
elif command -v dnf &> /dev/null; then
    echo "  Detected: Fedora/RHEL"
    print_step "Installing system packages..."
    sudo dnf install -y -q \
        python3 python3-virtualenv python3-pip python3-gobject \
        portaudio-devel gobject-introspection-devel libappindicator-gtk3 \
        python3-qt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
elif command -v pacman &> /dev/null; then
    echo "  Detected: Arch Linux"
    print_step "Installing system packages..."
    sudo pacman -S --noconfirm --needed \
        python python-virtualenv python-pip python-gobject \
        portaudio gobject-introspection libappindicator-gtk3 \
        python-pyqt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
else
    print_warning "Could not detect package manager. Please install manually:"
    echo "  - python3, python3-venv, python3-gi, portaudio, PyQt5, ydotool"
fi

# Check Python
print_step "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 is required but not installed."
    exit 1
fi

# Model selection
select_model

# Create/check virtual environment
print_step "Setting up Python virtual environment..."
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    python3 -m venv --system-site-packages "$SCRIPT_DIR/.venv"
    print_success "Virtual environment created"
else
    print_success "Virtual environment exists"
fi

# Install Python dependencies
print_step "Installing Python dependencies (this may take a while)..."
"$SCRIPT_DIR/.venv/bin/pip" install -q --upgrade pip 2>/dev/null || true
"$SCRIPT_DIR/.venv/bin/pip" install -q -e "$SCRIPT_DIR" 2>/dev/null || \
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || true
print_success "Python dependencies installed"

# Save selected model to config
print_step "Configuring WhisperLayer..."
mkdir -p "$HOME/.config/whisperlayer"
CONFIG_FILE="$HOME/.config/whisperlayer/settings.json"

if [ -f "$CONFIG_FILE" ]; then
    # Update existing config with new model
    "$SCRIPT_DIR/.venv/bin/python" -c "
import json
with open('$CONFIG_FILE', 'r') as f:
    config = json.load(f)
config['model'] = '$SELECTED_MODEL'
with open('$CONFIG_FILE', 'w') as f:
    json.dump(config, f, indent=2)
print('Updated model in existing config')
" 2>/dev/null || echo '{"model": "'$SELECTED_MODEL'"}' > "$CONFIG_FILE"
else
    echo '{"model": "'$SELECTED_MODEL'"}' > "$CONFIG_FILE"
fi
print_success "Model set to: $SELECTED_MODEL"

# Check if user is in input group
print_step "Checking group permissions..."
if ! groups | grep -q input; then
    echo ""
    print_warning "Adding user to 'input' group (required for global hotkeys)..."
    sudo usermod -aG input "$USER"
    print_warning "You'll need to LOG OUT and back in for this to take effect."
else
    print_success "User already in 'input' group"
fi

# Set up uinput permissions
print_step "Setting up uinput permissions..."
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    sudo bash -c 'echo "KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"" > /etc/udev/rules.d/99-uinput.rules'
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    print_success "uinput rules configured"
else
    print_success "uinput rules already exist"
fi

# Create directories
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.config/systemd/user"
mkdir -p "$HOME/.config/autostart"

# Install desktop file
print_step "Installing desktop launcher..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=WhisperLayer
Comment=Speech-to-Text Voice Typing
Exec=sg input -c "$SCRIPT_DIR/.venv/bin/python -m whisperlayer"
Icon=audio-input-microphone
Terminal=false
Type=Application
Categories=Utility;Accessibility;
Keywords=voice;speech;transcription;typing;stt;whisper;
StartupNotify=false
EOF
print_success "Desktop launcher installed"

# Install systemd service
print_step "Installing systemd service..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=WhisperLayer Speech-to-Text
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/sg input -c "$SCRIPT_DIR/.venv/bin/python -m whisperlayer"
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/%U

[Install]
WantedBy=default.target
EOF

# Reload systemd
systemctl --user daemon-reload 2>/dev/null || true
print_success "Systemd service installed"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Installation Complete! ✓            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "  WhisperLayer is ready to use!"
echo ""
echo -e "  ${BLUE}Model:${NC} $SELECTED_MODEL"
echo -e "  ${BLUE}Hotkey:${NC} Ctrl+Alt+F (default, change in Settings)"
echo ""
echo "  Launch options:"
echo "    • From Applications menu: Search 'WhisperLayer'"
echo "    • From terminal: whisperlayer"
echo "    • As service: systemctl --user start whisperlayer"
echo ""

# Ask about auto-start
echo -e "${YELLOW}═══════════════════════════════════════════════${NC}"
read -p "Enable auto-start on login? [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl --user enable whisperlayer 2>/dev/null || true
    print_success "Auto-start enabled"
else
    echo "  Skipped. Enable later with: systemctl --user enable whisperlayer"
fi

echo ""
if ! groups | grep -q input; then
    echo -e "${YELLOW}╔════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  IMPORTANT: Please log out and back in     ║${NC}"
    echo -e "${YELLOW}║  for group permissions to take effect!     ║${NC}"
    echo -e "${YELLOW}╚════════════════════════════════════════════╝${NC}"
    echo ""
fi

echo -e "${GREEN}Done! Enjoy WhisperLayer 🎤${NC}"
echo ""
