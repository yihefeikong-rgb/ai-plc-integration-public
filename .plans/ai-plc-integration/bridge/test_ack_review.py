import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("ack_review.py")
spec = importlib.util.spec_from_file_location("ack_review", MODULE_PATH)
ack_review = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ack_review)


class AckReviewTests(unittest.TestCase):
    def _write_state(self, bridge_dir: Path, state: dict) -> Path:
        state_file = bridge_dir / "state.json"
        state_file.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        return state_file

    def test_ack_pass_requires_reason(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            state_file = self._write_state(
                bridge_dir,
                {
                    "stage": "NEED_CODEX_REVIEW",
                    "run_id": "run-1",
                    "review_status": "",
                    "stop_rule": "PERMISSION_DENIED",
                    "blocked_reason": "2 permission request(s) denied",
                    "session_id": "session-1",
                },
            )

            with self.assertRaises(SystemExit):
                ack_review.ack_review(
                    bridge_dir=bridge_dir,
                    state_file=state_file,
                    run_id="run-1",
                    decision="PASS",
                    reason="",
                )

    def test_ack_pass_rejects_mismatched_run_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            state_file = self._write_state(
                bridge_dir,
                {
                    "stage": "NEED_CODEX_REVIEW",
                    "run_id": "run-1",
                    "review_status": "",
                    "stop_rule": "PERMISSION_DENIED",
                    "blocked_reason": "2 permission request(s) denied",
                    "session_id": "session-1",
                },
            )

            with self.assertRaises(SystemExit):
                ack_review.ack_review(
                    bridge_dir=bridge_dir,
                    state_file=state_file,
                    run_id="other-run",
                    decision="PASS",
                    reason="permission denial was expected",
                )

    def test_ack_pass_closes_current_run_without_executing_next_task(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            run_dir = bridge_dir / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            (run_dir / "claude_result.md").write_text(
                "\n".join(
                    [
                        "# Claude Code Execution Result",
                        "",
                        "## Task",
                        "",
                        "```",
                        "读取 bridge README 并总结 C-18 Stop Rule",
                        "```",
                    ]
                ),
                encoding="utf-8",
            )
            state_file = self._write_state(
                bridge_dir,
                {
                    "stage": "NEED_CODEX_REVIEW",
                    "owner": "codex",
                    "last_actor": "claude_code",
                    "run_id": "run-1",
                    "review_status": "",
                    "stop_rule": "PERMISSION_DENIED",
                    "blocked_reason": "2 permission request(s) denied",
                    "session_id": "session-1",
                    "session_reused": True,
                },
            )

            result = ack_review.ack_review(
                bridge_dir=bridge_dir,
                state_file=state_file,
                run_id="run-1",
                decision="PASS",
                reason="permission denial was expected for C-18 probe",
            )
            state = json.loads(state_file.read_text(encoding="utf-8"))
            next_action = (run_dir / "next_action.md").read_text(encoding="utf-8")

        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(state["stage"], "DONE")
        self.assertEqual(state["review_status"], "PASS")
        self.assertEqual(state["stop_rule"], "NONE")
        self.assertEqual(state["last_stop_rule"], "PERMISSION_DENIED")
        self.assertEqual(state["blocked_reason"], "")
        self.assertEqual(state["session_id"], "session-1")
        self.assertEqual(
            state["supervised_completed_tasks"],
            ["读取 bridge README 并总结 C-18 Stop Rule"],
        )
        self.assertIn("permission denial was expected for C-18 probe", next_action)
        self.assertIn("Manual review accepted", next_action)

    def test_ack_block_marks_state_blocked(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            run_dir = bridge_dir / "runs" / "run-1"
            run_dir.mkdir(parents=True)
            state_file = self._write_state(
                bridge_dir,
                {
                    "stage": "NEED_CODEX_REVIEW",
                    "run_id": "run-1",
                    "review_status": "",
                    "stop_rule": "PERMISSION_DENIED",
                    "blocked_reason": "2 permission request(s) denied",
                    "session_id": "session-1",
                },
            )

            ack_review.ack_review(
                bridge_dir=bridge_dir,
                state_file=state_file,
                run_id="run-1",
                decision="BLOCK",
                reason="permission denial was unexpected",
            )
            state = json.loads(state_file.read_text(encoding="utf-8"))
            next_action = (run_dir / "next_action.md").read_text(encoding="utf-8")

        self.assertEqual(state["stage"], "BLOCKED")
        self.assertEqual(state["review_status"], "BLOCK")
        self.assertEqual(state["stop_rule"], "PERMISSION_DENIED")
        self.assertIn("permission denial was unexpected", next_action)


if __name__ == "__main__":
    unittest.main()
