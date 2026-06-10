"""Frontend build gate — catches TypeScript errors before deploy."""
import subprocess
import pathlib
import pytest

FRONTEND_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "frontend"


@pytest.mark.skipif(
    not (FRONTEND_DIR / "node_modules").exists(),
    reason="Frontend node_modules not installed",
)
class TestFrontendBuild:
    def test_typescript_compiles(self):
        """Frontend TypeScript must compile without errors."""
        result = subprocess.run(
            ["npx", "tsc", "--noEmit"],
            cwd=FRONTEND_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"TypeScript compilation failed:\n{result.stdout}\n{result.stderr}"
        )
