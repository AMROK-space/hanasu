# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Hanasu, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email security concerns to: **security@amrok.space**
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 7 days
- **Resolution timeline:** Communicated after assessment

## Scope

### In Scope

- Code in this repository
- Installation scripts
- Dependencies (report upstream, but notify us)
- Configuration handling

### Out of Scope

- Social engineering attacks
- Attacks requiring physical access to user's machine
- Issues in third-party dependencies with existing CVEs (report upstream)

## Security Design

Hanasu is designed with privacy in mind:

- **Local processing only:** All audio is processed on-device using Whisper. No data is sent to external servers.
- **No cloud dependencies:** The only network activity is downloading the Whisper model from Hugging Face during setup.
- **Minimal permissions:** Only requires Accessibility permission for hotkey detection and text injection.
- **No credential storage:** Hanasu does not store any passwords, API keys, or authentication tokens.

## Configuration Notes

### Clipboard Usage

Hanasu uses the system clipboard to inject transcribed text (via Cmd+V simulation). Transcribed text briefly resides on the clipboard before being pasted. You can enable `clear_clipboard: true` in your config to clear the clipboard after each paste.

### Debug Logging

When `debug: true` is set in config, transcribed text is logged to `~/.hanasu/hanasu.log`. Set `debug: false` to disable this.

### Configuration Files

Configuration is stored in plaintext at `~/.hanasu/`. Do not store sensitive information in the dictionary or config files.
