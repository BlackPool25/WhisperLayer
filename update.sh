#!/usr/bin/env bash
# WhisperLayer Update Script
# Fetches releases from GitHub and allows user to select which version to install
# IMPORTANT: Run with 'bash update.sh' NOT 'sh update.sh'

set -e

# Ensure we're running with bash
if [ -z "${BASH_VERSION:-}" ]; then
    echo "Error: This script requires bash. Please run with: bash update.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_REPO="BlackPool25/WhisperLayer"
GITHUB_API="https://api.github.com/repos/$GITHUB_REPO/releases"
BACKUP_DIR="$HOME/.cache/whisperlayer-backup"

# Colors for pretty output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}   ${CYAN}WhisperLayer Updater${NC}                     ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}   Update to the latest version             ${BLUE}║${NC}"
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

# Check for required tools
check_dependencies() {
    local missing=()
    
    if ! command -v curl &> /dev/null; then
        missing+=("curl")
    fi
    
    if ! command -v jq &> /dev/null; then
        # jq is optional, we can use grep/sed fallback
        HAS_JQ=false
    else
        HAS_JQ=true
    fi
    
    if ! command -v tar &> /dev/null; then
        missing+=("tar")
    fi
    
    if [ ${#missing[@]} -gt 0 ]; then
        print_error "Missing required tools: ${missing[*]}"
        echo "  Please install them and try again."
        exit 1
    fi
}

# Fetch releases from GitHub API
fetch_releases() {
    print_step "Fetching available releases from GitHub..."
    
    RELEASES_JSON=$(curl -s -H "Accept: application/vnd.github+json" "$GITHUB_API" 2>/dev/null)
    
    if [ -z "$RELEASES_JSON" ] || [ "$RELEASES_JSON" = "[]" ]; then
        print_error "Failed to fetch releases. Check your internet connection."
        exit 1
    fi
    
    # Check for API rate limit
    if echo "$RELEASES_JSON" | grep -q "API rate limit exceeded"; then
        print_error "GitHub API rate limit exceeded. Please try again later."
        exit 1
    fi
}

# Parse releases and display menu
display_releases() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  Available Releases${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo ""
    
    if [ "$HAS_JQ" = true ]; then
        # Use jq for parsing
        RELEASE_COUNT=$(echo "$RELEASES_JSON" | jq 'length')
        
        if [ "$RELEASE_COUNT" -eq 0 ]; then
            print_warning "No releases found."
            exit 0
        fi
        
        # Limit to 10 most recent releases
        local max_display=10
        if [ "$RELEASE_COUNT" -gt "$max_display" ]; then
            RELEASE_COUNT=$max_display
        fi
        
        for i in $(seq 0 $((RELEASE_COUNT - 1))); do
            TAG=$(echo "$RELEASES_JSON" | jq -r ".[$i].tag_name")
            NAME=$(echo "$RELEASES_JSON" | jq -r ".[$i].name")
            PRERELEASE=$(echo "$RELEASES_JSON" | jq -r ".[$i].prerelease")
            PUBLISHED=$(echo "$RELEASES_JSON" | jq -r ".[$i].published_at" | cut -d'T' -f1)
            
            local idx=$((i + 1))
            local status=""
            if [ "$PRERELEASE" = "true" ]; then
                status="${YELLOW}(pre-release)${NC}"
            fi
            
            if [ $i -eq 0 ]; then
                echo -e "  ${GREEN}$idx)${NC} $TAG - $NAME $status ${GREEN}★ Latest${NC}"
            else
                echo -e "  $idx) $TAG - $NAME $status"
            fi
            echo -e "     Published: $PUBLISHED"
            echo ""
        done
    else
        # Fallback parsing without jq
        print_warning "jq not installed - using basic parsing"
        echo ""
        
        # Extract tag names using grep/sed
        TAGS=$(echo "$RELEASES_JSON" | grep -o '"tag_name":\s*"[^"]*"' | sed 's/"tag_name":\s*"//g' | sed 's/"//g' | head -10)
        
        local idx=1
        while IFS= read -r tag; do
            if [ -n "$tag" ]; then
                if [ $idx -eq 1 ]; then
                    echo -e "  ${GREEN}$idx)${NC} $tag ${GREEN}★ Latest${NC}"
                else
                    echo -e "  $idx) $tag"
                fi
                idx=$((idx + 1))
            fi
        done <<< "$TAGS"
        echo ""
    fi
}

# Get release info by index
get_release_info() {
    local index=$1
    
    if [ "$HAS_JQ" = true ]; then
        SELECTED_TAG=$(echo "$RELEASES_JSON" | jq -r ".[$((index - 1))].tag_name")
        SELECTED_TARBALL=$(echo "$RELEASES_JSON" | jq -r ".[$((index - 1))].tarball_url")
        SELECTED_NAME=$(echo "$RELEASES_JSON" | jq -r ".[$((index - 1))].name")
    else
        SELECTED_TAG=$(echo "$RELEASES_JSON" | grep -o '"tag_name":\s*"[^"]*"' | sed 's/"tag_name":\s*"//g' | sed 's/"//g' | sed -n "${index}p")
        SELECTED_TARBALL="https://github.com/$GITHUB_REPO/archive/refs/tags/$SELECTED_TAG.tar.gz"
        SELECTED_NAME="$SELECTED_TAG"
    fi
}

# Backup current configuration
backup_config() {
    local config_dir="$HOME/.config/whisperlayer"
    
    if [ -d "$config_dir" ]; then
        print_step "Backing up configuration..."
        mkdir -p "$BACKUP_DIR"
        cp -r "$config_dir" "$BACKUP_DIR/config-$(date +%Y%m%d-%H%M%S)"
        print_success "Configuration backed up to $BACKUP_DIR"
    fi
}

# Download and extract release
download_release() {
    local tarball_url="$1"
    local tag="$2"
    
    print_step "Downloading release $tag..."
    
    local temp_dir=$(mktemp -d)
    local tarball_file="$temp_dir/release.tar.gz"
    
    # Download tarball
    if ! curl -L -o "$tarball_file" "$tarball_url" 2>/dev/null; then
        print_error "Failed to download release"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    # Verify it's a valid tarball
    if ! tar -tzf "$tarball_file" > /dev/null 2>&1; then
        print_error "Downloaded file is not a valid tarball"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    print_success "Download complete"
    
    # Extract
    print_step "Extracting release..."
    cd "$temp_dir"
    tar -xzf "$tarball_file"
    
    # Find the extracted directory (GitHub creates a folder like repo-tag)
    EXTRACTED_DIR=$(find . -maxdepth 1 -type d -name "WhisperLayer-*" -o -name "whisperlayer-*" | head -1)
    
    if [ -z "$EXTRACTED_DIR" ]; then
        # Try alternative pattern
        EXTRACTED_DIR=$(find . -maxdepth 1 -type d ! -name "." | head -1)
    fi
    
    if [ -z "$EXTRACTED_DIR" ] || [ ! -d "$EXTRACTED_DIR" ]; then
        print_error "Failed to find extracted directory"
        rm -rf "$temp_dir"
        exit 1
    fi
    
    print_success "Extracted to $EXTRACTED_DIR"
    
    # Return the paths
    TEMP_DIR="$temp_dir"
    RELEASE_DIR="$temp_dir/$EXTRACTED_DIR"
}

# Install the new release
install_release() {
    local release_dir="$1"
    
    print_step "Installing new version..."
    
    # Stop current services
    if systemctl --user is-active --quiet whisperlayer 2>/dev/null; then
        print_step "Stopping current service..."
        systemctl --user stop whisperlayer 2>/dev/null || true
    fi
    
    # Copy new files (preserve .venv if exists)
    print_step "Updating files..."
    
    # Backup .venv if it exists and user wants to keep it
    local venv_backed_up=false
    if [ -d "$SCRIPT_DIR/.venv" ]; then
        echo ""
        print_warning "Virtual environment (.venv) exists."
        read -p "  Keep current virtual environment? [Y/n]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            mv "$SCRIPT_DIR/.venv" "/tmp/whisperlayer-venv-backup-$$"
            venv_backed_up=true
        fi
    fi
    
    # Copy all files except .git
    rsync -av --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        "$release_dir/" "$SCRIPT_DIR/" 2>/dev/null || \
        cp -r "$release_dir/"* "$SCRIPT_DIR/"
    
    # Restore .venv if backed up
    if [ "$venv_backed_up" = true ]; then
        mv "/tmp/whisperlayer-venv-backup-$$" "$SCRIPT_DIR/.venv"
        print_success "Restored virtual environment"
    fi
    
    # Make scripts executable
    chmod +x "$SCRIPT_DIR/"*.sh 2>/dev/null || true
    
    print_success "Files updated"
    
    # Run install.sh to update dependencies
    if [ -f "$SCRIPT_DIR/install.sh" ]; then
        echo ""
        print_warning "Running install.sh to update dependencies..."
        echo ""
        bash "$SCRIPT_DIR/install.sh"
    fi
}

# Cleanup temp files
cleanup() {
    if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

# Set up trap for cleanup
trap cleanup EXIT

# Parse arguments
LIST_ONLY=false
AUTO_LATEST=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --list|--list-only)
            LIST_ONLY=true
            shift
            ;;
        --latest)
            AUTO_LATEST=true
            shift
            ;;
        -h|--help)
            echo "WhisperLayer Updater"
            echo ""
            echo "Usage: bash update.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --list, --list-only    Only list available releases, don't install"
            echo "  --latest               Automatically install the latest release"
            echo "  -h, --help             Show this help message"
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
check_dependencies
fetch_releases
display_releases

if [ "$LIST_ONLY" = true ]; then
    echo "Use 'bash update.sh' to install a release."
    exit 0
fi

# Get user selection
if [ "$AUTO_LATEST" = true ]; then
    SELECTION=1
    echo -e "Auto-selecting latest release..."
else
    if [ "$HAS_JQ" = true ]; then
        RELEASE_COUNT=$(echo "$RELEASES_JSON" | jq 'length')
        if [ "$RELEASE_COUNT" -gt 10 ]; then
            RELEASE_COUNT=10
        fi
    else
        RELEASE_COUNT=$(echo "$RELEASES_JSON" | grep -o '"tag_name"' | wc -l)
        if [ "$RELEASE_COUNT" -gt 10 ]; then
            RELEASE_COUNT=10
        fi
    fi
    
    read -p "Select release [1-$RELEASE_COUNT, default=1]: " SELECTION
    SELECTION=${SELECTION:-1}
    
    # Validate selection
    if ! [[ "$SELECTION" =~ ^[0-9]+$ ]] || [ "$SELECTION" -lt 1 ] || [ "$SELECTION" -gt "$RELEASE_COUNT" ]; then
        print_error "Invalid selection"
        exit 1
    fi
fi

# Get release info
get_release_info "$SELECTION"

echo ""
echo -e "Selected: ${GREEN}$SELECTED_NAME${NC} ($SELECTED_TAG)"
echo ""

# Confirm installation
if [ "$AUTO_LATEST" = false ]; then
    read -p "Install this version? [Y/n]: " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        echo "Update cancelled."
        exit 0
    fi
fi

# Backup and install
backup_config
download_release "$SELECTED_TARBALL" "$SELECTED_TAG"
install_release "$RELEASE_DIR"

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║        Update Complete! ✓                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
echo ""
echo "  WhisperLayer has been updated to: $SELECTED_TAG"
echo ""
echo "  To start:"
echo "    • Run: whisperlayer"
echo "    • Or: systemctl --user start whisperlayer"
echo ""
echo -e "${GREEN}Done!${NC}"
echo ""
