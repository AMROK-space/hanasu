#!/bin/bash
# Hanasu install script (developer guard)
#
# This script exists to catch developers who run ./scripts/install.sh from
# a development checkout. The canonical installer is the bootstrap script
# at the repo root, which should be run via curl | bash.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CANONICAL_SRC="$HOME/.hanasu/src"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

error() { echo -e "${RED}Error:${NC} $1" >&2; }
info() { echo -e "${GREEN}==>${NC} $1"; }

# Check if we're running from the canonical install location
if [[ "$PROJECT_DIR" == "$CANONICAL_SRC" ]]; then
    # We're in the installed location - run the bootstrap installer
    info "Running from installed location, delegating to bootstrap installer..."
    exec "$PROJECT_DIR/install.sh"
fi

# We're in a development checkout
if [[ -d "$PROJECT_DIR/.git" ]]; then
    error "This appears to be a development checkout at:"
    echo "  $PROJECT_DIR"
    echo
    echo "For development, run manually:"
    echo "  cd $PROJECT_DIR"
    echo "  uv sync"
    echo "  uv run hanasu run"
    echo
    echo "For system install (auto-start, Spotlight, CLI):"
    echo "  curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
    echo
    echo "This installs to ~/.hanasu/ and sets up:"
    echo "  - Auto-start on login (LaunchAgent)"
    echo "  - Spotlight integration (/Applications/Hanasu.app)"
    echo "  - CLI command (hanasu)"
    exit 1
fi

# Unknown state - shouldn't happen
error "Cannot determine installation context"
echo "Please use the bootstrap installer:"
echo "  curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash"
exit 1
