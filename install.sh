#!/bin/bash
# Hanasu bootstrap installer
# Usage: curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash
#
# This installer:
# - Downloads Hanasu to ~/.hanasu/src/
# - Creates a virtual environment at ~/.hanasu/.venv/
# - Sets up auto-start via LaunchAgent
# - Creates /Applications/Hanasu.app for Spotlight
# - Writes an install manifest for clean uninstall

set -euo pipefail

INSTALL_DIR="$HOME/.hanasu"
SRC_DIR="$INSTALL_DIR/src"
VENV_DIR="$INSTALL_DIR/.venv"
MANIFEST_FILE="$INSTALL_DIR/.install-manifest"
LEGACY_DIR="$HOME/.hanasu-src"
REPO_URL="https://github.com/amrok-space/hanasu.git"

LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.amrok.hanasu.plist"
PLIST_PATH="$LAUNCH_AGENT_DIR/$PLIST_NAME"
APP_PATH="/Applications/Hanasu.app"
CLI_LINK="$HOME/.local/bin/hanasu"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

info() { echo -e "${GREEN}==>${NC} $1"; }
warn() { echo -e "${YELLOW}Warning:${NC} $1"; }
error() { echo -e "${RED}Error:${NC} $1" >&2; }

echo "Hanasu Installer"
echo "================"
echo "Local voice-to-text dictation for macOS"
echo "By AMROK (https://amrok.space)"
echo

# -----------------------------------------------------------------------------
# Platform checks
# -----------------------------------------------------------------------------

if [[ "$(uname)" != "Darwin" ]]; then
    error "Hanasu only supports macOS"
    exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
    warn "Hanasu works best on Apple Silicon (M1/M2/M3)"
    echo "Intel Macs may have slower performance"
    echo
fi

# -----------------------------------------------------------------------------
# Detect if running from a development checkout
# -----------------------------------------------------------------------------

# BASH_SOURCE is empty when running via curl | bash
if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    SCRIPT_DIR=""
fi

if [[ -n "$SCRIPT_DIR" && -d "$SCRIPT_DIR/.git" && -f "$SCRIPT_DIR/pyproject.toml" ]]; then
    # Check if this is the canonical install location
    if [[ "$SCRIPT_DIR" != "$SRC_DIR" ]]; then
        error "This appears to be a development checkout at: $SCRIPT_DIR"
        echo
        echo "For development, run manually:"
        echo "  cd $SCRIPT_DIR"
        echo "  uv sync && uv run hanasu run"
        echo
        echo "For system install (auto-start, Spotlight, CLI):"
        echo "  curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
        echo
        echo "This installs to ~/.hanasu/ and sets up auto-start."
        exit 1
    fi
fi

# -----------------------------------------------------------------------------
# Check for existing installation
# -----------------------------------------------------------------------------

if [[ -f "$MANIFEST_FILE" ]]; then
    info "Found existing installation"
    echo "Options:"
    echo "  1) Update - pull latest changes and reinstall"
    echo "  2) Reinstall - remove and install fresh"
    echo "  3) Abort"
    echo
    read -p "Choice [1/2/3]: " choice
    case "$choice" in
        1)
            info "Updating existing installation..."
            cd "$SRC_DIR"
            git pull --quiet
            # Continue with install to update venv and artifacts
            ;;
        2)
            info "Removing existing installation..."
            "$SRC_DIR/scripts/uninstall.sh" --yes 2>/dev/null || true
            ;;
        3)
            echo "Aborted."
            exit 0
            ;;
        *)
            error "Invalid choice"
            exit 1
            ;;
    esac
fi

# -----------------------------------------------------------------------------
# Detect and migrate legacy installation
# -----------------------------------------------------------------------------

if [[ -d "$LEGACY_DIR" && ! -d "$SRC_DIR" ]]; then
    warn "Found legacy installation at $LEGACY_DIR"
    echo "Migrating to $SRC_DIR..."
    mkdir -p "$INSTALL_DIR"
    mv "$LEGACY_DIR" "$SRC_DIR"
    info "Migration complete"
fi

# Check for LaunchAgent pointing elsewhere
if [[ -f "$PLIST_PATH" ]]; then
    CURRENT_TARGET=$(grep -A1 'ProgramArguments' "$PLIST_PATH" 2>/dev/null | grep string | head -1 | sed 's/.*<string>\(.*\)<\/string>.*/\1/' || true)
    if [[ -n "$CURRENT_TARGET" && "$CURRENT_TARGET" != "$VENV_DIR/bin/hanasu" ]]; then
        warn "Found LaunchAgent pointing to: $CURRENT_TARGET"
        echo "This will be updated to point to ~/.hanasu/"
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        rm -f "$PLIST_PATH"
    fi
fi

# -----------------------------------------------------------------------------
# Install uv if needed
# -----------------------------------------------------------------------------

if ! command -v uv &> /dev/null; then
    info "Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# -----------------------------------------------------------------------------
# Clone or update source
# -----------------------------------------------------------------------------

mkdir -p "$INSTALL_DIR"

if [[ -d "$SRC_DIR/.git" ]]; then
    info "Source exists, pulling latest..."
    cd "$SRC_DIR"
    git pull --quiet
else
    info "Downloading Hanasu..."
    rm -rf "$SRC_DIR"
    git clone --quiet "$REPO_URL" "$SRC_DIR"
fi

cd "$SRC_DIR"

# -----------------------------------------------------------------------------
# Create virtual environment and install
# -----------------------------------------------------------------------------

info "Installing dependencies..."
uv sync --quiet

# -----------------------------------------------------------------------------
# Run first-time setup
# -----------------------------------------------------------------------------

info "Running setup..."
uv run hanasu setup 2>/dev/null || true

# -----------------------------------------------------------------------------
# Write install manifest (before creating artifacts)
# -----------------------------------------------------------------------------

info "Writing install manifest..."
cat > "$MANIFEST_FILE" << EOF
{
  "version": 1,
  "installed_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "artifacts": [
    {"type": "directory", "path": "$SRC_DIR"},
    {"type": "directory", "path": "$VENV_DIR"},
    {"type": "file", "path": "$PLIST_PATH"},
    {"type": "directory", "path": "$APP_PATH"},
    {"type": "symlink", "path": "$CLI_LINK"}
  ]
}
EOF

# -----------------------------------------------------------------------------
# Create LaunchAgent
# -----------------------------------------------------------------------------

info "Setting up auto-start..."
mkdir -p "$LAUNCH_AGENT_DIR"

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.amrok.hanasu</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/hanasu</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>$INSTALL_DIR/hanasu.log</string>
    <key>StandardErrorPath</key>
    <string>$INSTALL_DIR/hanasu.log</string>
</dict>
</plist>
EOF

launchctl load "$PLIST_PATH" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Create .app bundle
# -----------------------------------------------------------------------------

info "Creating application bundle..."
rm -rf "$APP_PATH"
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# Get version from Python package
VERSION=$(uv run python -c "import hanasu; print(hanasu.__version__)" 2>/dev/null || echo "0.1.0")

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
    <string>$VERSION</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

cat > "$APP_PATH/Contents/MacOS/hanasu" << EOF
#!/bin/bash
exec "$VENV_DIR/bin/hanasu"
EOF
chmod +x "$APP_PATH/Contents/MacOS/hanasu"

# -----------------------------------------------------------------------------
# Create CLI symlink and ensure PATH
# -----------------------------------------------------------------------------

info "Setting up CLI..."
mkdir -p "$(dirname "$CLI_LINK")"
ln -sf "$VENV_DIR/bin/hanasu" "$CLI_LINK"

# Add ~/.local/bin to PATH in shell config if not already there
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
SHELL_CONFIGS=("$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile")
PATH_ADDED=false

for config in "${SHELL_CONFIGS[@]}"; do
    if [[ -f "$config" ]]; then
        if ! grep -q '\.local/bin' "$config" 2>/dev/null; then
            echo "" >> "$config"
            echo "# Added by Hanasu installer" >> "$config"
            echo "$PATH_LINE" >> "$config"
            PATH_ADDED=true
            info "Added ~/.local/bin to PATH in $config"
        fi
    fi
done

# Create .zshrc if it doesn't exist (macOS default shell)
if [[ ! -f "$HOME/.zshrc" ]]; then
    echo "# Added by Hanasu installer" > "$HOME/.zshrc"
    echo "$PATH_LINE" >> "$HOME/.zshrc"
    PATH_ADDED=true
    info "Created ~/.zshrc with PATH"
fi

# Export for current session
export PATH="$HOME/.local/bin:$PATH"

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------

echo
echo "========================================="
echo "Installation complete!"
echo
echo "IMPORTANT: Grant Accessibility permission"
echo "  System Settings → Privacy & Security → Accessibility"
echo "  Enable access for Terminal or Python"
echo
echo "Hanasu will start automatically on login."
echo "Look for the microphone icon in your menu bar."
echo
echo "To restart after quitting:"
echo "  - Search 'Hanasu' in Spotlight (Cmd+Space)"
echo "  - Or run: hanasu"
echo
if [[ "$PATH_ADDED" == "true" ]]; then
    echo "NOTE: Run 'source ~/.zshrc' or open a new terminal for CLI."
    echo
fi
echo "To uninstall:"
echo "  ~/.hanasu/src/scripts/uninstall.sh"
echo "========================================="
