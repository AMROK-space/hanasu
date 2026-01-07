# Hanasu

Local voice-to-text dictation for macOS using Whisper. By [AMROK](https://amrok.space).

**Hanasu** (話す) means "to speak" in Japanese.

## Features

- **Local processing** - Your audio never leaves your device
- **Fast** - Uses Apple Silicon MLX for hardware-accelerated inference
- **Simple** - Hold a hotkey to record, release to type
- **Menu bar app** - Always accessible, easy to quit/restart

## Requirements

- macOS 12+ with Apple Silicon (M1/M2/M3)
- ~1GB disk space for the Whisper model

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash
```

This installs to `~/.hanasu/` and sets up:
- Auto-start on login (LaunchAgent)
- Spotlight integration (/Applications/Hanasu.app)
- CLI command (`hanasu`)

**Important:** Grant Accessibility permission when prompted:
- System Settings → Privacy & Security → Accessibility
- Enable access for Terminal or Python

## Usage

After installation, Hanasu runs in your menu bar:
- **Microphone icon (🎤)** - Ready, waiting for hotkey
- **Red circle (🔴)** - Recording in progress
- **Click the icon** - See hotkey, change hotkey, check for updates, or quit

**Default hotkey:** `Cmd+Option+V` (hold to record, release to type)

To restart after quitting:
- Search "Hanasu" in Spotlight (Cmd+Space)
- Or run: `hanasu`

## Configuration

Edit `~/.hanasu/config.json`:

```json
{
  "hotkey": "cmd+alt+v",
  "model": "small",
  "language": "en",
  "audio_device": null,
  "debug": false,
  "clear_clipboard": false
}
```

### Options

- **hotkey**: Key combination to trigger recording
- **model**: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- **language**: Language code (e.g., `en`, `es`, `fr`)
- **audio_device**: Specific microphone name, or `null` for system default
- **debug**: Enable verbose logging (logs transcribed text to `~/.hanasu/hanasu.log`)
- **clear_clipboard**: Clear clipboard after pasting transcribed text

## Custom Dictionary

Add custom terms and replacements in `~/.hanasu/dictionary.json`:

```json
{
  "terms": ["AMROK", "Arvin", "MLX"],
  "replacements": {
    "amrock": "AMROK",
    "arvin x": "Arvin X"
  }
}
```

## Uninstall

```bash
~/.hanasu/src/scripts/uninstall.sh
```

Options:
- `--yes` - Skip confirmation prompts
- `--keep-config` - Preserve config.json

## CLI Commands

```bash
hanasu              # Start the app (normally auto-starts on login)
hanasu --status     # Show configuration and status
hanasu setup        # Run first-time setup
hanasu update       # Update to latest version
hanasu doctor       # Check installation health
hanasu transcribe <file> [--vtt] [--large]  # Transcribe audio file
```

## Development

For development, clone and run directly (does not install system-wide):

```bash
git clone https://github.com/amrok-space/hanasu.git
cd hanasu
uv sync
uv run hanasu
```

## Troubleshooting

### Check installation health

```bash
hanasu doctor
```

This verifies all components are correctly installed and configured.

### "Accessibility permission not granted"
1. Open System Settings → Privacy & Security → Accessibility
2. Find and enable the Terminal app or Python executable
3. Restart Hanasu

### No audio input
1. Check `hanasu --status` for available microphones
2. Verify your microphone works in other apps
3. Set specific device in config: `"audio_device": "AirPods Pro"`

### Transcription is slow
- Try a smaller model: `"model": "base"` or `"model": "tiny"`
- Ensure you're on Apple Silicon for MLX acceleration

## License

MIT

---

Made with ❤️ by [AMROK](https://amrok.space)
