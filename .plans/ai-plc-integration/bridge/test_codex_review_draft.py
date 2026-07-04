import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("codex_review_draft.py")
spec = importlib.util.spec_from_file_location("codex_review_draft", MODULE_PATH)
codex_review_draft = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(codex_review_draft)


class CodexReviewDraftTests(unittest.TestCase):
    def test_generate_review_draft_writes_draft_without_closing_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            run_id = "run-1"
            run_dir = bridge_dir / "runs" / run_id
            run_dir.mkdir(parents=True)
            state_file = bridge_dir / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "current_task": "C-14: cc-haha WS task runner MVP",
                        "stage": "NEED_CODEX_REVIEW",
                        "owner": "codex",
                        "run_id": run_id,
                        "review_status": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "claude_result.md").write_text(
                "\n".join(
                    [
                        "# Claude Code Execution Result",
                        "",
                        "- **Summary**: success",
                        "- **status**: OK",
                        "",
                        "## Event Log",
                        "",
                        "| # | type | detail |",
                        "|---|------|--------|",
                        "| 1 | message_complete | in=1 out=1 |",
                    ]
                ),
                encoding="utf-8",
            )

            result_path = codex_review_draft.generate_review_draft(
                bridge_dir=bridge_dir,
                state_file=state_file,
            )

            content = result_path.read_text(encoding="utf-8")
            state = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertIn("**Result**: PASS DRAFT", content)
        self.assertIn("Human final decision required", content)
        self.assertEqual(state["stage"], "NEED_CODEX_REVIEW")
        self.assertEqual(state["review_status"], "")

    def test_generate_review_draft_marks_denied_permissions_as_conditional(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            run_id = "run-2"
            run_dir = bridge_dir / "runs" / run_id
            run_dir.mkdir(parents=True)
            state_file = bridge_dir / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "current_task": "C-16 permission allowlist",
                        "stage": "NEED_CODEX_REVIEW",
                        "owner": "codex",
                        "run_id": run_id,
                        "review_status": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "claude_result.md").write_text(
                "\n".join(
                    [
                        "# Claude Code Execution Result",
                        "",
                        "- **Summary**: completed with 2 permission(s) denied",
                        "- **status**: OK",
                    ]
                ),
                encoding="utf-8",
            )

            result_path = codex_review_draft.generate_review_draft(
                bridge_dir=bridge_dir,
                state_file=state_file,
            )

            content = result_path.read_text(encoding="utf-8")

        self.assertIn("**Result**: CONDITIONAL PASS DRAFT", content)
        self.assertIn("permissions were denied", content)

    def test_generate_review_draft_does_not_overwrite_existing_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bridge_dir = Path(temp_dir)
            run_id = "run-3"
            run_dir = bridge_dir / "runs" / run_id
            run_dir.mkdir(parents=True)
            state_file = bridge_dir / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "current_task": "C-17 review draft",
                        "stage": "NEED_CODEX_REVIEW",
                        "owner": "codex",
                        "run_id": run_id,
                        "review_status": "",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (run_dir / "claude_result.md").write_text(
                "- **Summary**: success\n- **status**: OK\nmessage_complete\n",
                encoding="utf-8",
            )
            review_path = run_dir / "codex_review.md"
            review_path.write_text("existing human review\n", encoding="utf-8")

            with self.assertRaises(SystemExit):
                codex_review_draft.generate_review_draft(
                    bridge_dir=bridge_dir,
                    state_file=state_file,
                )

            content = review_path.read_text(encoding="utf-8")

        self.assertEqual(content, "existing human review\n")


if __name__ == "__main__":
    unittest.main()
