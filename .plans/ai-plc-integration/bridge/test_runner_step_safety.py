import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


BRIDGE_DIR = Path(__file__).resolve().parent
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

MODULE_PATH = BRIDGE_DIR / "runner_step.py"
spec = importlib.util.spec_from_file_location("runner_step", MODULE_PATH)
runner_step = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runner_step)


class RunnerStepSafetyTests(unittest.TestCase):
    def test_resolve_claude_command_rejects_extra_arguments(self):
        with self.assertRaises(runner_step.RunnerCommandError):
            runner_step.resolve_claude_command("claude --dangerously-skip-permissions")

    def test_resolve_claude_command_rejects_other_executable(self):
        with self.assertRaises(runner_step.RunnerCommandError):
            runner_step.resolve_claude_command("powershell")

    def test_resolve_claude_command_resolves_allowlisted_executable(self):
        with patch.object(runner_step.shutil, "which", return_value=r"C:\tools\claude.cmd"):
            argv = runner_step.resolve_claude_command("claude")

        self.assertEqual(argv, [r"C:\tools\claude.cmd"])

    def test_run_claude_cli_pins_project_root_and_disables_shell(self):
        completed = Mock(returncode=0)
        with patch.object(runner_step.subprocess, "run", return_value=completed) as run_mock:
            result = runner_step.run_claude_cli([r"C:\tools\claude.cmd"], "review this task")

        self.assertIs(result, completed)
        run_mock.assert_called_once_with(
            [r"C:\tools\claude.cmd"],
            input="review this task",
            text=True,
            shell=False,
            cwd=str(runner_step.PROJECT_ROOT),
            timeout=3600,
        )


if __name__ == "__main__":
    unittest.main()
