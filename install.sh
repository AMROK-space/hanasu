#!/bin/bash
# Hanasu one-liner installer
# Usage: curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash

set -e

INSTALL_DIR="$HOME/.hanasu-src"
REPO_URL="https://github.com/amrok-space/hanasu.git"

echo "Hanasu Installer"
echo "================"
echo "Local voice-to-text dictation for macOS"
echo "By AMROK (https://amrok.space)"
echo

# Check for macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: Hanasu only supports macOS"
    exit 1
fi

# Check for Apple Silicon
if [[ "$(uname -m)" != "arm64" ]]; then
    echo "Warning: Hanasu works best on Apple Silicon (M1/M2/M3)"
    echo "Intel Macs may have slower performance"
    echo
fi

# Clone or update repo
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    git pull --quiet
else
    echo "Downloading Hanasu..."
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Run the full installer
exec ./scripts/install.sh
