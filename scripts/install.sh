#!/bin/bash
# Install script for Hanasu - by AMROK

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.amrok.hanasu.plist"
APP_NAME="Hanasu.app"
APP_PATH="/Applications/$APP_NAME"

echo "Hanasu Installer"
echo "================"
echo "Local voice-to-text dictation for macOS"
echo "By AMROK (https://amrok.space)"
echo

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Navigate to project directory
cd "$PROJECT_DIR"

# Sync dependencies
echo "Installing dependencies..."
uv sync --no-editable

# Run setup
echo
echo "Running first-time setup..."
uv run hanasu setup

# Create LaunchAgent
echo
echo "Setting up auto-start..."
mkdir -p "$LAUNCH_AGENT_DIR"

cat > "$LAUNCH_AGENT_DIR/$PLIST_NAME" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.amrok.hanasu</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/.venv/bin/hanasu</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$HOME/.hanasu/hanasu.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/.hanasu/hanasu.log</string>
</dict>
</plist>
EOF

echo "Created LaunchAgent: $LAUNCH_AGENT_DIR/$PLIST_NAME"

# Load the LaunchAgent
launchctl load "$LAUNCH_AGENT_DIR/$PLIST_NAME" 2>/dev/null || true

# Create .app bundle for Spotlight access
echo
echo "Creating application bundle..."
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Create Info.plist
cat > "$APP_PATH/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>hanasu</string>
    <key>CFBundleIdentifier</key>
    <string>com.amrok.hanasu</string>
    <key>CFBundleName</key>
    <string>Hanasu</string>
    <key>CFBundleDisplayName</key>
    <string>Hanasu</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

# Create launcher script
cat > "$APP_PATH/Contents/MacOS/hanasu" << EOF
#!/bin/bash
exec "$PROJECT_DIR/.venv/bin/hanasu"
EOF
chmod +x "$APP_PATH/Contents/MacOS/hanasu"

echo "Created: $APP_PATH"

echo
echo "========================================="
echo "Installation complete!"
echo
echo "IMPORTANT: Grant Accessibility permission"
echo "  System Settings -> Privacy & Security -> Accessibility"
echo "  Enable access for Terminal or Python"
echo
echo "Hanasu will start automatically on login."
echo "Look for the microphone icon in your menu bar."
echo "Click it to see status or quit."
echo
echo "To restart after quitting:"
echo "  - Search 'Hanasu' in Spotlight (Cmd+Space)"
echo "  - Or open from /Applications"
echo "========================================="
