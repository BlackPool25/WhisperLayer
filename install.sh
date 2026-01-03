#!/bin/bash
# VoiceType Installation Script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_FILE="$HOME/.local/share/applications/voicetype.desktop"
SERVICE_FILE="$HOME/.config/systemd/user/voicetype.service"
AUTOSTART_FILE="$HOME/.config/autostart/voicetype.desktop"

echo "=========================================="
echo "VoiceType Installer"
echo "=========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

# Check for virtual environment
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv --system-site-packages "$SCRIPT_DIR/.venv"
fi

# Install Python dependencies
echo "Installing Python dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt" 2>/dev/null || true

# Check if user is in input group
if ! groups | grep -q input; then
    echo ""
    echo "Adding user to 'input' group (required for global hotkeys)..."
    sudo usermod -aG input "$USER"
    echo "NOTE: You'll need to log out and back in for this to take effect."
fi

# Set up uinput permissions
echo "Setting up uinput permissions..."
if [ ! -f /etc/udev/rules.d/99-uinput.rules ]; then
    sudo bash -c 'echo "KERNEL==\"uinput\", MODE=\"0660\", GROUP=\"input\"" > /etc/udev/rules.d/99-uinput.rules'
    sudo udevadm control --reload-rules
    sudo udevadm trigger
fi

# Create directories
mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.config/systemd/user"
mkdir -p "$HOME/.config/autostart"
mkdir -p "$HOME/.config/voicetype"

# Install desktop file
echo "Installing desktop launcher..."
cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=VoiceType
Comment=Speech-to-Text Voice Typing
Exec=sg input -c "$SCRIPT_DIR/.venv/bin/python -m voicetype"
Icon=audio-input-microphone
Terminal=false
Type=Application
Categories=Utility;Accessibility;
Keywords=voice;speech;transcription;typing;stt;
StartupNotify=false
EOF

# Install systemd service
echo "Installing systemd service..."
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=VoiceType Speech-to-Text
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/sg input -c "$SCRIPT_DIR/.venv/bin/python -m voicetype"
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=/run/user/%U

[Install]
WantedBy=default.target
EOF

# Reload systemd
systemctl --user daemon-reload

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "VoiceType is now available in your applications menu."
echo ""
echo "To enable auto-start on login:"
echo "  systemctl --user enable voicetype"
echo ""
echo "To start VoiceType now:"
echo "  systemctl --user start voicetype"
echo ""
echo "Or launch from your applications menu."
echo ""

# Ask about auto-start
read -p "Enable auto-start on login? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl --user enable voicetype
    echo "Auto-start enabled!"
fi

echo ""
echo "Done! Enjoy VoiceType 🎤"
