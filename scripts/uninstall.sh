#!/bin/bash
# Uninstall script for Hanasu

set -e

LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.amrok.hanasu.plist"
CONFIG_DIR="$HOME/.hanasu"
APP_PATH="/Applications/Hanasu.app"

echo "Hanasu Uninstaller"
echo "=================="
echo

# Stop and unload LaunchAgent
if [ -f "$LAUNCH_AGENT_DIR/$PLIST_NAME" ]; then
    echo "Stopping Hanasu service..."
    launchctl unload "$LAUNCH_AGENT_DIR/$PLIST_NAME" 2>/dev/null || true
    rm "$LAUNCH_AGENT_DIR/$PLIST_NAME"
    echo "Removed LaunchAgent"
else
    echo "LaunchAgent not found (already removed or never installed)"
fi

# Remove app bundle
if [ -d "$APP_PATH" ]; then
    rm -rf "$APP_PATH"
    echo "Removed $APP_PATH"
fi

# Ask about config removal
echo
read -p "Remove config directory ($CONFIG_DIR)? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        echo "Removed config directory"
    else
        echo "Config directory not found"
    fi
else
    echo "Keeping config directory"
fi

echo
echo "========================================="
echo "Uninstall complete!"
echo
echo "Note: The project files and virtual environment"
echo "are still in place. To fully remove, delete the"
echo "project directory manually."
echo "========================================="
