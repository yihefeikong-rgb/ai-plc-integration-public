import os
import subprocess
import sys
from pathlib import Path


def test_default_collection_excludes_hardware_and_desktop_tests():
    root = Path(__file__).parents[2]
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "tests/test_download_flow.py" not in result.stdout
    assert "tests/test_robot_mcp.py" not in result.stdout
    assert "mcp-servers/tia-mcp/archived" not in result.stdout
