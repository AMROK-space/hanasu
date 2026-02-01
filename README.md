# Hanasu

Local voice-to-text dictation for macOS using Whisper. By [AMROK](https://amrok.space).

**Hanasu** (話す) means "to speak" in Japanese.

## Features

- **Local processing** - Your audio never leaves your device
- **Fast** - Uses Apple Silicon MLX for hardware-accelerated inference
- **Simple** - Hold a hotkey to record, release to type
- **Menu bar app** - Always accessible, easy to quit/restart
- **File transcription** - Transcribe existing audio/video files via menu or CLI

## Requirements

- macOS 12+ with Apple Silicon (M1/M2/M3)
- ~1GB disk space for the Whisper model

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/amrok-space/hanasu/main/install.sh | bash
```

This installs to `~/.hanasu/` and sets up:
- Spotlight integration (/Applications/Hanasu.app)
- CLI command (`hanasu`)

**Important:** Grant Accessibility permission when prompted:
- System Settings → Privacy & Security → Accessibility
- Enable access for Terminal or Python

## Usage

After installation, Hanasu runs in your menu bar:
- **Microphone icon (🎤)** - Ready, waiting for hotkey
- **Red circle (🔴)** - Recording in progress
- **Click the icon** - See hotkey, change hotkey, transcribe files, check for updates, or quit

### Menu Bar Options

- **Hotkey** - Shows current hotkey for push-to-talk
- **Change Hotkey...** - Opens dialog to set a new hotkey
- **Model** - Submenu to switch between Whisper models (see below)
- **Transcribe File...** - Opens file picker to transcribe audio/video files (see below)
- **Version / Update** - Shows current version and update status
- **Quit** - Stops Hanasu

### Model Selection (Menu)

Switch between Whisper models directly from the menu bar without restarting:

- **tiny** (~75MB) - Fastest, lower accuracy
- **base** (~140MB) - Fast, decent accuracy
- **small** (~460MB) - Balanced speed/accuracy (default)
- **medium** (~1.5GB) - Better accuracy, slower
- **large** (~3GB) - Best accuracy, slowest

The menu shows:
- **●** Current model
- **✓** Models already downloaded (cached)
- **↓** Models that need to be downloaded

Selecting an uncached model will prompt to confirm before downloading.

### Transcribe File (Menu)

Select "Transcribe File..." from the menu to transcribe existing audio or video files:

1. Select an audio/video file (mp3, wav, m4a, mp4, mov, mkv, avi, webm)
2. Choose output format: Plain Text (.txt) or VTT Subtitles (.vtt)
3. Choose save location

Transcription runs in the background using the configured Whisper model. The last used output directory is remembered.

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
  "clear_clipboard": false,
  "last_output_dir": null
}
```

### Options

- **hotkey**: Key combination to trigger recording
- **model**: Whisper model size (`tiny`, `base`, `small`, `medium`, `large`)
- **language**: Language code (e.g., `en`, `es`, `fr`)
- **audio_device**: Specific microphone name, or `null` for system default
- **debug**: Enable verbose console output (logs are always written to `~/Library/Logs/Hanasu/hanasu.log`)
- **clear_clipboard**: Clear clipboard after pasting transcribed text
- **last_output_dir**: Remembered directory for file transcription saves (auto-updated)

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
hanasu              # Start the app (runs in menu bar)
hanasu --status     # Show configuration and status
hanasu setup        # Run first-time setup
hanasu update       # Update to latest version
hanasu doctor       # Check installation health
hanasu transcribe <file> [--vtt] [--large] [-o FILE]  # Transcribe audio or video file
```

### Transcribe Command (CLI)

Transcribe audio files directly or extract and transcribe audio from video files:

```bash
# Audio files (mp3, wav, m4a, etc.)
hanasu transcribe recording.m4a

# Video files (mp4, mov, mkv, etc.) - requires ffmpeg
hanasu transcribe meeting.mp4

# Output as VTT subtitles
hanasu transcribe video.mp4 --vtt

# Use large model for better accuracy
hanasu transcribe audio.wav --large

# Write output to a file instead of stdout
hanasu transcribe audio.wav -o transcript.txt
hanasu transcribe video.mp4 --vtt -o subtitles.vtt
```

**Video transcription requires ffmpeg.** Install with:
```bash
brew install ffmpeg
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

### Menu bar icon not visible
On MacBooks with a notch (M1 Pro/Max and later), the menu bar icon may be hidden if you have too many menu bar items. macOS silently hides overflow icons behind the notch with no indication.

To fix:
1. Remove or hide some menu bar icons (use a tool like [Bartender](https://www.macbartender.com/) or [Hidden Bar](https://github.com/dwarvesf/hidden))
2. Verify Hanasu is running: `hanasu --status`
3. The app is still functional even if the icon is hidden - the hotkey still works
=======
### View logs
Hanasu logs to `~/Library/Logs/Hanasu/hanasu.log`. View recent logs with:
```bash
tail -f ~/Library/Logs/Hanasu/hanasu.log
```

Or open in Console.app: Applications → Utilities → Console → File → Open → select `hanasu.log`

## License

MIT

---

Made with ❤️ by [AMROK](https://amrok.space)
