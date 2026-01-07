#!/bin/bash
# Hanasu uninstaller
#
# Removes exactly what the installer created, based on the install manifest.
# Safe to run multiple times (idempotent).

set -euo pipefail

INSTALL_DIR="$HOME/.hanasu"
MANIFEST_FILE="$INSTALL_DIR/.install-manifest"
CONFIG_FILE="$INSTALL_DIR/config.json"
LOG_FILE="$INSTALL_DIR/hanasu.log"

# Fallback paths if no manifest exists
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.amrok.hanasu.plist"
PLIST_PATH="$LAUNCH_AGENT_DIR/$PLIST_NAME"
APP_PATH="/Applications/Hanasu.app"
CLI_LINK="$HOME/.local/bin/hanasu"
LEGACY_DIR="$HOME/.hanasu-src"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

info() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}Warning:${NC} $1"; }
error() { echo -e "${RED}Error:${NC} $1" >&2; }

# Parse arguments
AUTO_YES=false
KEEP_CONFIG=false
for arg in "$@"; do
    case "$arg" in
        --yes|-y) AUTO_YES=true ;;
        --keep-config) KEEP_CONFIG=true ;;
        --help|-h)
            echo "Hanasu Uninstaller"
            echo
            echo "Usage: uninstall.sh [OPTIONS]"
            echo
            echo "Options:"
            echo "  --yes, -y       Skip confirmation prompts"
            echo "  --keep-config   Keep config.json (user settings)"
            echo "  --help, -h      Show this help"
            exit 0
            ;;
    esac
done

echo "Hanasu Uninstaller"
echo "=================="
echo

# -----------------------------------------------------------------------------
# Check for installation
# -----------------------------------------------------------------------------

FOUND_ANYTHING=false

if [[ -f "$MANIFEST_FILE" ]]; then
    info "Found install manifest"
    FOUND_ANYTHING=true
elif [[ -f "$PLIST_PATH" ]] || [[ -d "$APP_PATH" ]] || [[ -d "$INSTALL_DIR" ]] || [[ -d "$LEGACY_DIR" ]]; then
    warn "No manifest found, but found installation artifacts"
    FOUND_ANYTHING=true
fi

if [[ "$FOUND_ANYTHING" == "false" ]]; then
    info "No Hanasu installation found. Nothing to remove."
    exit 0
fi

# -----------------------------------------------------------------------------
# Confirmation
# -----------------------------------------------------------------------------

if [[ "$AUTO_YES" == "false" ]]; then
    echo "This will remove:"
    [[ -d "$INSTALL_DIR/src" ]] && echo "  - Source code: $INSTALL_DIR/src/"
    [[ -d "$INSTALL_DIR/.venv" ]] && echo "  - Virtual environment: $INSTALL_DIR/.venv/"
    [[ -f "$PLIST_PATH" ]] && echo "  - LaunchAgent: $PLIST_PATH"
    [[ -d "$APP_PATH" ]] && echo "  - Application: $APP_PATH"
    [[ -L "$CLI_LINK" ]] && echo "  - CLI symlink: $CLI_LINK"
    [[ -d "$LEGACY_DIR" ]] && echo "  - Legacy install: $LEGACY_DIR"
    echo
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

# -----------------------------------------------------------------------------
# Stop running instance
# -----------------------------------------------------------------------------

info "Stopping Hanasu..."
pkill -f "hanasu" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Unload and remove LaunchAgent
# -----------------------------------------------------------------------------

if [[ -f "$PLIST_PATH" ]]; then
    info "Removing LaunchAgent..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
    rm -f "$PLIST_PATH"
fi

# -----------------------------------------------------------------------------
# Remove application bundle
# -----------------------------------------------------------------------------

if [[ -d "$APP_PATH" ]]; then
    info "Removing application bundle..."
    rm -rf "$APP_PATH"
fi

# -----------------------------------------------------------------------------
# Remove CLI symlink
# -----------------------------------------------------------------------------

if [[ -L "$CLI_LINK" ]]; then
    info "Removing CLI symlink..."
    rm -f "$CLI_LINK"
fi

# -----------------------------------------------------------------------------
# Remove source and venv
# -----------------------------------------------------------------------------

if [[ -d "$INSTALL_DIR/src" ]]; then
    info "Removing source code..."
    rm -rf "$INSTALL_DIR/src"
fi

if [[ -d "$INSTALL_DIR/.venv" ]]; then
    info "Removing virtual environment..."
    rm -rf "$INSTALL_DIR/.venv"
fi

# -----------------------------------------------------------------------------
# Remove legacy installation
# -----------------------------------------------------------------------------

if [[ -d "$LEGACY_DIR" ]]; then
    info "Removing legacy installation..."
    rm -rf "$LEGACY_DIR"
fi

# -----------------------------------------------------------------------------
# Handle user data
# -----------------------------------------------------------------------------

if [[ -f "$CONFIG_FILE" && "$KEEP_CONFIG" == "false" ]]; then
    if [[ "$AUTO_YES" == "true" ]]; then
        info "Keeping config file (use rm manually to remove)"
    else
        echo
        read -p "Remove config file ($CONFIG_FILE)? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$CONFIG_FILE"
            info "Removed config file"
        else
            info "Keeping config file"
        fi
    fi
fi

# Leave log file - it's harmless and might be useful for debugging

# -----------------------------------------------------------------------------
# Remove manifest
# -----------------------------------------------------------------------------

rm -f "$MANIFEST_FILE"

# -----------------------------------------------------------------------------
# Clean up empty directory
# -----------------------------------------------------------------------------

if [[ -d "$INSTALL_DIR" ]]; then
    # Check if directory is empty (except for log file and maybe config)
    REMAINING=$(ls -A "$INSTALL_DIR" 2>/dev/null | grep -v "^hanasu.log$" | grep -v "^config.json$" || true)
    if [[ -z "$REMAINING" ]]; then
        # Only log and possibly config remain
        if [[ ! -f "$CONFIG_FILE" ]]; then
            # Just log file or empty - safe to remove
            rm -rf "$INSTALL_DIR"
            info "Removed $INSTALL_DIR"
        else
            info "Keeping $INSTALL_DIR (contains config.json)"
        fi
    else
        warn "Keeping $INSTALL_DIR (contains unexpected files)"
    fi
fi

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------

echo
echo "========================================="
echo "Uninstall complete!"
echo
if [[ -f "$CONFIG_FILE" ]]; then
    echo "Your config file was preserved at:"
    echo "  $CONFIG_FILE"
    echo
fi
echo "To reinstall:"
echo "  curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
echo "========================================="
