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

Or clone and install manually:

```bash
git clone https://github.com/amrok-space/hanasu.git
cd hanasu
./scripts/install.sh
```

**Important:** Grant Accessibility permission when prompted:
- System Settings → Privacy & Security → Accessibility
- Enable access for Terminal or Python

## Usage

After installation, Hanasu runs in your menu bar:
- **Microphone icon (🎤)** - Ready, waiting for hotkey
- **Red circle (🔴)** - Recording in progress
- **Click the icon** - See hotkey, quit the app

**Default hotkey:** `Cmd+Option+V` (hold to record, release to type)

To restart after quitting:
- Search "Hanasu" in Spotlight (Cmd+Space)
- Or open from /Applications

## Configuration

Edit `~/.hanasu/config.json`:

```json
{
  "hotkey": "cmd+alt+v",
  "model": "small",
  "language": "en",
  "audio_device": null,
  "debug": false
}
```

### Options

- **hotkey**: Key combination to trigger recording
- **model**: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- **language**: Language code (e.g., `en`, `es`, `fr`)
- **audio_device**: Specific microphone name, or `null` for system default
- **debug**: Enable verbose logging

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
./scripts/uninstall.sh
```

Or manually:
```bash
rm -rf /Applications/Hanasu.app
rm ~/Library/LaunchAgents/com.amrok.hanasu.plist
rm -rf ~/.hanasu
```

## Troubleshooting

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
