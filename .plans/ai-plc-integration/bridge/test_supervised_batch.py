import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("supervised_batch.py")
spec = importlib.util.spec_from_file_location("supervised_batch", MODULE_PATH)
supervised_batch = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(supervised_batch)


class SupervisedBatchTests(unittest.TestCase):
    def test_gate_blocks_non_none_stop_rule(self):
        state = {
            "stage": "NEED_CODEX_REVIEW",
            "review_status": "",
            "stop_rule": "PERMISSION_DENIED",
            "blocked_reason": "2 permission request(s) denied",
            "session_id": "session-1",
        }

        gate = supervised_batch.evaluate_supervised_gate(state)

        self.assertFalse(gate["allowed"])
        self.assertEqual(gate["code"], "STOP_RULE_ACTIVE")
        self.assertIn("PERMISSION_DENIED", gate["reason"])

    def test_gate_blocks_missing_session_id(self):
        state = {
            "stage": "DONE",
            "review_status": "PASS",
            "stop_rule": "NONE",
            "session_id": "",
        }

        gate = supervised_batch.evaluate_supervised_gate(state)

        self.assertFalse(gate["allowed"])
        self.assertEqual(gate["code"], "MISSING_SESSION")

    def test_gate_blocks_unreviewed_state(self):
        state = {
            "stage": "NEED_CODEX_REVIEW",
            "review_status": "",
            "stop_rule": "NONE",
            "session_id": "session-1",
        }

        gate = supervised_batch.evaluate_supervised_gate(state)

        self.assertFalse(gate["allowed"])
        self.assertEqual(gate["code"], "HUMAN_REVIEW_REQUIRED")

    def test_gate_allows_after_human_pass(self):
        state = {
            "stage": "DONE",
            "review_status": "PASS",
            "stop_rule": "NONE",
            "session_id": "session-1",
        }

        gate = supervised_batch.evaluate_supervised_gate(state)

        self.assertTrue(gate["allowed"])
        self.assertEqual(gate["code"], "READY")

    def test_load_task_queue_ignores_comments_and_blank_lines(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            task_file = Path(temp_dir) / "tasks.txt"
            task_file.write_text(
                "\n".join(
                    [
                        "# C-19 low-risk queue",
                        "",
                        "读取 bridge README 并总结",
                        "  ",
                        "读取 progress 当前边界",
                    ]
                ),
                encoding="utf-8",
            )

            tasks = supervised_batch.load_task_queue(task_file)

        self.assertEqual(tasks, ["读取 bridge README 并总结", "读取 progress 当前边界"])

    def test_build_next_step_uses_existing_session_without_new_session_flag(self):
        step = supervised_batch.build_next_step(
            {"session_id": "session-1"},
            "读取 bridge README 并总结",
        )

        self.assertIn("--session-id session-1", step)
        self.assertNotIn("--new-session", step)

    def test_run_supervised_dry_run_does_not_modify_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            state_file = bridge_dir / "state.json"
            task_file = bridge_dir / "tasks.txt"
            original_state = {
                "stage": "DONE",
                "review_status": "PASS",
                "stop_rule": "NONE",
                "session_id": "session-1",
            }
            state_file.write_text(json.dumps(original_state), encoding="utf-8")
            task_file.write_text("读取 bridge README 并总结\n", encoding="utf-8")

            result = supervised_batch.run_supervised_dry_run(
                state_file=state_file,
                task_file=task_file,
            )
            state_after = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertTrue(result["allowed"])
        self.assertEqual(state_after, original_state)

    def test_run_supervised_dry_run_skips_completed_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            state_file = bridge_dir / "state.json"
            task_file = bridge_dir / "tasks.txt"
            state_file.write_text(
                json.dumps(
                    {
                        "stage": "DONE",
                        "review_status": "PASS",
                        "stop_rule": "NONE",
                        "session_id": "session-1",
                        "supervised_completed_tasks": ["task one"],
                    }
                ),
                encoding="utf-8",
            )
            task_file.write_text("task one\ntask two\n", encoding="utf-8")

            result = supervised_batch.run_supervised_dry_run(
                state_file=state_file,
                task_file=task_file,
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["next_task"], "task two")

    def test_run_supervised_dry_run_reports_all_tasks_done(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            state_file = bridge_dir / "state.json"
            task_file = bridge_dir / "tasks.txt"
            state_file.write_text(
                json.dumps(
                    {
                        "stage": "DONE",
                        "review_status": "PASS",
                        "stop_rule": "NONE",
                        "session_id": "session-1",
                        "supervised_completed_tasks": ["task one", "task two"],
                    }
                ),
                encoding="utf-8",
            )
            task_file.write_text("task one\ntask two\n", encoding="utf-8")

            result = supervised_batch.run_supervised_dry_run(
                state_file=state_file,
                task_file=task_file,
            )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "ALL_TASKS_DONE")
        self.assertEqual(result["next_task"], "")


if __name__ == "__main__":
    unittest.main()
