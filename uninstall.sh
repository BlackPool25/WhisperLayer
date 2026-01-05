#!/usr/bin/env bash
# WhisperLayer Uninstallation Script
# IMPORTANT: Run with 'bash uninstall.sh' NOT 'sh uninstall.sh'

set -e

# Ensure we're running with bash
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Error: This script requires bash. Please run with: bash uninstall.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   ${YELLOW}WhisperLayer Uninstaller${NC}                 ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}   Safe removal of WhisperLayer            ${BLUE}║${NC}"
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

# Paths
DESKTOP_FILE="$HOME/.local/share/applications/whisperlayer.desktop"
SERVICE_FILE="$HOME/.config/systemd/user/whisperlayer.service"
AUTOSTART_FILE="$HOME/.config/autostart/whisperlayer.desktop"
CONFIG_DIR="$HOME/.config/whisperlayer"
VENV_DIR="$SCRIPT_DIR/.venv"
UDEV_RULES="/etc/udev/rules.d/99-uinput.rules"

# Verify we're in the right directory
verify_directory() {
    if [ ! -f "$SCRIPT_DIR/install.sh" ] || [ ! -d "$SCRIPT_DIR/whisperlayer" ]; then
        print_error "This script must be run from the WhisperLayer installation directory."
        print_error "Expected to find: install.sh and whisperlayer/ folder"
        exit 1
    fi
}

# Stop running services
stop_services() {
    print_step "Stopping WhisperLayer services..."
    
    # Stop systemd service if running
    if systemctl --user is-active --quiet whisperlayer 2>/dev/null; then
        systemctl --user stop whisperlayer 2>/dev/null || true
        print_success "Stopped systemd service"
    fi
    
    # Disable autostart
    if systemctl --user is-enabled --quiet whisperlayer 2>/dev/null; then
        systemctl --user disable whisperlayer 2>/dev/null || true
        print_success "Disabled autostart"
    fi
    
    # Kill any running instances
    if pgrep -f "python.*whisperlayer" > /dev/null 2>&1; then
        pkill -f "python.*whisperlayer" 2>/dev/null || true
        print_success "Stopped running instances"
    fi
}

# Remove systemd service file
remove_service() {
    print_step "Removing systemd service..."
    if [ -f "$SERVICE_FILE" ]; then
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload 2>/dev/null || true
        print_success "Removed systemd service"
    else
        echo "  (already removed)"
    fi
}

# Remove desktop launcher
remove_desktop_launcher() {
    print_step "Removing desktop launcher..."
    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        print_success "Removed desktop launcher"
    else
        echo "  (already removed)"
    fi
}

# Remove autostart entry
remove_autostart() {
    print_step "Removing autostart entry..."
    if [ -f "$AUTOSTART_FILE" ]; then
        rm -f "$AUTOSTART_FILE"
        print_success "Removed autostart entry"
    else
        echo "  (already removed)"
    fi
}

# Remove virtual environment (optional)
remove_venv() {
    if [ -d "$VENV_DIR" ]; then
        echo ""
        print_warning "Virtual environment found at: $VENV_DIR"
        echo "  This contains installed Python packages (~500MB-2GB depending on model)."
        read -p "  Remove virtual environment? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
            print_success "Removed virtual environment"
        else
            echo "  Kept virtual environment"
        fi
    fi
}

# Remove configuration (optional)
remove_config() {
    if [ -d "$CONFIG_DIR" ]; then
        echo ""
        print_warning "Configuration directory found at: $CONFIG_DIR"
        echo "  This contains your settings (model choice, hotkey, etc.)."
        read -p "  Remove configuration? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$CONFIG_DIR"
            print_success "Removed configuration"
        else
            echo "  Kept configuration (can be reused on reinstall)"
        fi
    fi
}

# Remove udev rules (optional, requires sudo)
remove_udev_rules() {
    if [ -f "$UDEV_RULES" ]; then
        echo ""
        print_warning "udev rules found at: $UDEV_RULES"
        echo "  These allow input device access for global hotkeys."
        echo "  Other applications may also use these rules."
        read -p "  Remove udev rules? (requires sudo) [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            if sudo rm -f "$UDEV_RULES" 2>/dev/null; then
                sudo udevadm control --reload-rules 2>/dev/null || true
                sudo udevadm trigger 2>/dev/null || true
                print_success "Removed udev rules"
            else
                print_error "Failed to remove udev rules (permission denied)"
            fi
        else
            echo "  Kept udev rules"
        fi
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        Uninstall Complete! ✓               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  The following were removed:"
    echo "    • Systemd service"
    echo "    • Desktop launcher"
    echo "    • Autostart entry"
    echo ""
    echo "  Source code remains at: $SCRIPT_DIR"
    echo "  You can delete it manually if desired:"
    echo "    rm -rf \"$SCRIPT_DIR\""
    echo ""
    print_warning "If you added yourself to the 'input' group during installation,"
    echo "  you may remove yourself with: sudo gpasswd -d \$USER input"
    echo ""
}

# Full uninstall mode (no prompts)
full_uninstall() {
    print_step "Running full uninstall (removing all components)..."
    
    stop_services
    remove_service
    remove_desktop_launcher
    remove_autostart
    
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        print_success "Removed virtual environment"
    fi
    
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        print_success "Removed configuration"
    fi
    
    print_summary
}

# Parse arguments
FULL_MODE=false
KEEP_CONFIG=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --all|--full)
            FULL_MODE=true
            shift
            ;;
        --keep-config)
            KEEP_CONFIG=true
            shift
            ;;
        -h|--help)
            echo "WhisperLayer Uninstaller"
            echo ""
            echo "Usage: bash uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --all, --full     Remove everything without prompts"
            echo "  --keep-config     Keep configuration when using --all"
            echo "  -h, --help        Show this help message"
            echo ""
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information."
            exit 1
            ;;
    esac
done

# Main execution
print_header
verify_directory

if [ "$FULL_MODE" = true ]; then
    if [ "$KEEP_CONFIG" = true ]; then
        stop_services
        remove_service
        remove_desktop_launcher
        remove_autostart
        if [ -d "$VENV_DIR" ]; then
            rm -rf "$VENV_DIR"
            print_success "Removed virtual environment"
        fi
        print_summary
    else
        full_uninstall
    fi
else
    # Interactive mode
    echo "This will uninstall WhisperLayer from your system."
    echo ""
    read -p "Continue? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        exit 0
    fi
    
    stop_services
    remove_service
    remove_desktop_launcher
    remove_autostart
    remove_venv
    remove_config
    remove_udev_rules
    print_summary
fi

echo -e "${GREEN}Done!${NC}"
echo ""
