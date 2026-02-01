# Noridoc: scripts

Path: @/scripts

### Overview

Installation and uninstallation shell scripts for managing Hanasu system installations. These scripts handle the lifecycle of installed artifacts including the application bundle, CLI symlink, and configuration directory.

### How it fits into the larger codebase

The `scripts/` directory contains operational scripts that are distinct from the root `install.sh` bootstrap installer:

| Script | Purpose |
|--------|---------|
| `install.sh` | Developer guard that redirects to the canonical installer |
| `uninstall.sh` | Removes all installed artifacts based on the install manifest |

The root `install.sh` at `@/install.sh` is the canonical bootstrap installer meant to be run via `curl | bash`. The `scripts/install.sh` exists to catch developers who mistakenly run `./scripts/install.sh` from a development checkout.

### Core Implementation

**Developer Guard (`scripts/install.sh`)**:
- Checks if running from canonical install location (`~/.hanasu/src`)
- If in a development checkout (has `.git` directory), prints error and exits
- If in installed location, delegates to the root `install.sh`

**Uninstaller (`scripts/uninstall.sh`)**:
- Reads `~/.hanasu/.install-manifest` to identify installed artifacts
- Stops any running Hanasu process via `pkill`
- Removes: LaunchAgent plist, application bundle, CLI symlink, source directory, virtual environment
- Optionally preserves `config.json` via `--keep-config` flag
- Handles legacy installations at `~/.hanasu-src`

### Things to Know

**Install manifest**: The installer writes a JSON manifest to `~/.hanasu/.install-manifest` containing paths to all created artifacts. The uninstaller uses this for clean removal rather than hardcoded paths.

**LaunchAgent removal**: The installer explicitly removes any existing LaunchAgent plist because auto-start functionality was removed. Legacy installations may have this plist file.

**Idempotent uninstall**: The uninstaller can be run multiple times safely and will report "No Hanasu installation found" if nothing exists.

Created and maintained by Nori.
