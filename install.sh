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
AUTOSTART_DIR="$HOME/.config/autostart"
AUTOSTART_FILE="$AUTOSTART_DIR/whisperlayer.desktop"

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

# Detect if running inside a container (Docker, Podman, etc.)
detect_container() {
    if [ -f /.dockerenv ]; then
        return 0
    fi
    if grep -qE 'docker|lxc|containerd|podman' /proc/1/cgroup 2>/dev/null; then
        return 0
    fi
    if [ -n "$container" ]; then
        return 0
    fi
    return 1
}

IN_CONTAINER=false
if detect_container; then
    IN_CONTAINER=true
fi

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
    echo "  Detected: Debian/Ubuntu (apt)"
    print_step "Installing system packages (may require sudo password)..."
    sudo apt-get update -qq 2>/dev/null || true
    sudo apt-get install -y -qq \
        python3 python3-venv python3-pip python3-gi \
        portaudio19-dev libgirepository1.0-dev gir1.2-appindicator3-0.1 \
        python3-pyqt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
        
elif command -v dnf &> /dev/null; then
    echo "  Detected: Fedora/RHEL (dnf)"
    print_step "Installing system packages..."
    sudo dnf install -y -q \
        python3 python3-virtualenv python3-pip python3-gobject \
        portaudio-devel gobject-introspection-devel libappindicator-gtk3 \
        python3-qt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
        
elif command -v pacman &> /dev/null; then
    echo "  Detected: Arch Linux (pacman)"
    print_step "Installing system packages..."
    sudo pacman -S --noconfirm --needed \
        python python-virtualenv python-pip python-gobject \
        portaudio gobject-introspection libappindicator-gtk3 \
        python-pyqt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"

elif command -v zypper &> /dev/null; then
    echo "  Detected: OpenSUSE (zypper)"
    print_step "Installing system packages..."
    sudo zypper install -y \
        python3 python3-virtualenv python3-pip python3-gobject \
        portaudio-devel gobject-introspection-devel libappindicator3-1 \
        python3-qt5 ydotool 2>/dev/null || print_warning "Some packages may already be installed"
        
else
    print_warning "Could not detect supported package manager (apt, dnf, pacman, zypper)."
    echo "  Please manually install: python3, python3-venv, python3-gi, portaudio, PyQt5, ydotool"
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
print_step "Checking permissions (input group)..."
if [ "$IN_CONTAINER" = true ]; then
    print_warning "Running in container - checking input group exists..."
    if ! getent group input > /dev/null 2>&1; then
        groupadd input 2>/dev/null || true
    fi
else
    if ! groups | grep -q input; then
        echo ""
        print_warning "Adding user to 'input' group (required for global hotkeys)..."
        sudo usermod -aG input "$USER"
        print_warning "NOTE: You MUST Log out and Log back to apply this permission!"
    else
        print_success "User already in 'input' group"
    fi
fi

# Set up uinput/ydotool permissions securely
print_step "Setting up ydotool/uinput permissions..."
if [ "$IN_CONTAINER" = true ]; then
    print_warning "Running in container - skipping udev checks"
else
    if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
        echo "  Creating udev rule for uinput access..."
        sudo bash -c 'echo "KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"" > /etc/udev/rules.d/99-uinput.rules'
        sudo udevadm control --reload-rules
        sudo udevadm trigger
        print_success "uinput permissions configured"
    else
        print_success "uinput rules already exist"
    fi
    
    # Check /dev/uinput access
    if [ ! -r /dev/uinput ] || [ ! -w /dev/uinput ]; then
        print_warning "Current user cannot access /dev/uinput yet."
        print_warning "Please REBOOT or LOG OUT/IN after install."
    fi
fi

# Desktop Integration
if [ "$IN_CONTAINER" = true ]; then
    print_warning "Running in container - skipping desktop integration"
else
    mkdir -p "$HOME/.local/share/applications"
    mkdir -p "$HOME/.config/systemd/user"
    mkdir -p "$AUTOSTART_DIR"

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
    chmod +x "$DESKTOP_FILE"
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
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Installation Complete! ✓            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "  WhisperLayer is ready to use!"
echo ""
echo -e "  ${BLUE}Model:${NC} $SELECTED_MODEL"
echo -e "  ${BLUE}Hotkey:${NC} Ctrl+Alt+F (default)"
echo ""

# Ask about auto-start (skip in containers)
if [ "$IN_CONTAINER" = true ]; then
    print_warning "Container detected - skipping auto-start"
else
    echo -e "${YELLOW}═══════════════════════════════════════════════${NC}"
    read -p "Enable auto-start on login? (Recommended) [Y/n]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        # 1. Enable Systemd service
        if systemctl --user enable whisperlayer 2>/dev/null; then
            print_success "Auto-start enabled (Systemd)"
        else
            # 2. Fallback to XDG Autostart
            cp "$DESKTOP_FILE" "$AUTOSTART_FILE"
            print_success "Auto-start enabled (XDG Autostart fallback)"
        fi
    else
        echo "  Skipped."
    fi
fi

echo ""
if [ "$IN_CONTAINER" != true ] && ! groups | grep -q input; then
    echo -e "${RED}IMPORTANT: You must LOG OUT and back in to fix permissions!${NC}"
fi

echo -e "${GREEN}Done! Run 'whisperlayer' to start.${NC}"
echo ""
