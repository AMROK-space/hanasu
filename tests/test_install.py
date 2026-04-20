"""Tests for install script launcher generation."""

import ast
import re
from pathlib import Path

INSTALL_SCRIPT = Path(__file__).parent.parent / "install.sh"


class TestAppLauncher:
    """Test that the .app launcher is a Python script, not a bash+exec wrapper."""

    def _extract_launcher_template(self) -> str:
        """Extract the launcher heredoc from install.sh."""
        content = INSTALL_SCRIPT.read_text()

        # Find the launcher heredoc: cat > "$APP_PATH/Contents/MacOS/hanasu" << EOF
        pattern = r'cat > "\$APP_PATH/Contents/MacOS/hanasu" << \'?EOF\'?\n(.*?)\nEOF'
        match = re.search(pattern, content, re.DOTALL)
        assert match, "Could not find launcher heredoc in install.sh"
        return match.group(1)

    def test_launcher_is_not_bash_exec(self):
        """The .app launcher must not use bash+exec (breaks window server on macOS 26)."""
        launcher = self._extract_launcher_template()
        assert "#!/bin/bash" not in launcher, (
            "Launcher uses bash — this breaks the window server connection on macOS 26. "
            "Use a Python shebang instead."
        )
        assert "exec " not in launcher, (
            "Launcher uses exec — this breaks the window server connection on macOS 26."
        )

    def test_launcher_uses_python_shebang(self):
        """The .app launcher must use a Python shebang for direct execution."""
        launcher = self._extract_launcher_template()
        first_line = launcher.strip().split("\n")[0]
        # The heredoc template may contain shell variables like $VENV_DIR/bin/python3
        assert first_line.startswith("#!"), (
            f"Launcher shebang is '{first_line}' — expected a shebang line."
        )
        assert "python" in first_line or "VENV" in first_line, (
            f"Launcher shebang is '{first_line}' — expected a Python interpreter path "
            "(or shell variable pointing to one)."
        )

    def test_launcher_imports_and_calls_main(self):
        """The .app launcher must import and call hanasu.main:main."""
        launcher = self._extract_launcher_template()
        # Replace shell variables with placeholder paths for syntax checking
        launcher_code = launcher.replace("$VENV_DIR", "/tmp/fake-venv")
        launcher_code = launcher_code.replace("$SRC_DIR", "/tmp/fake-src")
        # Strip the shebang line for ast parsing
        lines = launcher_code.strip().split("\n")
        code_lines = [line for line in lines if not line.startswith("#!")]
        code = "\n".join(code_lines)

        # Should be valid Python syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise AssertionError(f"Launcher is not valid Python: {e}") from e

        # Should import from hanasu.main
        assert "hanasu.main" in launcher, "Launcher must import from hanasu.main"
        # Should call main()
        assert "main()" in launcher, "Launcher must call main()"
