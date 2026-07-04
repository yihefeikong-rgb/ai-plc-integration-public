import importlib.util
import json
import tempfile
import unittest
from datetime import datetime as real_datetime
from pathlib import Path
from unittest.mock import Mock, patch


MODULE_PATH = Path(__file__).with_name("ws_task_runner.py")
spec = importlib.util.spec_from_file_location("ws_task_runner", MODULE_PATH)
ws_task_runner = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ws_task_runner)


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps({"sessionId": "session-1"}).encode("utf-8")


class CreateSessionTests(unittest.TestCase):
    def test_create_session_sends_project_root_work_dir(self):
        captured = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse()

        result = None
        with patch.object(ws_task_runner, "urlopen", fake_urlopen):
            result = ws_task_runner.create_session("http://127.0.0.1:3456")

        expected_project_root = str(MODULE_PATH.resolve().parents[3])
        self.assertTrue(result["ok"])
        self.assertEqual(captured["url"], "http://127.0.0.1:3456/api/sessions")
        self.assertEqual(
            captured["body"],
            {"workDir": expected_project_root, "permissionMode": "default"},
        )
        self.assertEqual(captured["timeout"], ws_task_runner.SESSION_CREATE_TIMEOUT)

    def test_generate_run_id_is_unique_within_same_second(self):
        fake_datetime = Mock()
        fake_datetime.now.side_effect = [
            real_datetime(2026, 7, 4, 14, 38, 55, 123000),
            real_datetime(2026, 7, 4, 14, 38, 55, 456000),
        ]

        with patch.object(ws_task_runner, "datetime", fake_datetime):
            run_id_1 = ws_task_runner.generate_run_id("C-14: cc-haha WS task runner MVP")
            run_id_2 = ws_task_runner.generate_run_id("C-14: cc-haha WS task runner MVP")

        self.assertNotEqual(run_id_1, run_id_2)

    def test_resolve_session_reuses_existing_session_without_post(self):
        create_session_mock = Mock()

        with patch.object(ws_task_runner, "create_session", create_session_mock):
            result = ws_task_runner.resolve_session(
                "http://127.0.0.1:3456",
                reuse_session_id="existing-session",
            )

        create_session_mock.assert_not_called()
        self.assertTrue(result["ok"])
        self.assertTrue(result["reused"])
        self.assertEqual(result["session_id"], "existing-session")

    def test_update_state_json_records_session_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"

            with patch.object(ws_task_runner, "STATE_FILE", state_file):
                ws_task_runner.update_state_json(
                    "C-14: cc-haha WS task runner MVP",
                    "run-1",
                    session_id="session-1",
                    session_reused=True,
                )

            state = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertEqual(state["session_id"], "session-1")
        self.assertTrue(state["session_reused"])

    def test_update_state_json_leaves_blocked_reason_empty_without_stop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"

            with patch.object(ws_task_runner, "STATE_FILE", state_file):
                ws_task_runner.update_state_json(
                    "C-14: cc-haha WS task runner MVP",
                    "run-1",
                    stop_rule={
                        "code": "NONE",
                        "stop": False,
                        "reason": "no stop rule triggered",
                    },
                )

            state = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertEqual(state["stop_rule"], "NONE")
        self.assertEqual(state["blocked_reason"], "")

    def test_update_state_json_preserves_supervised_completed_tasks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "supervised_completed_tasks": ["task one"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(ws_task_runner, "STATE_FILE", state_file):
                ws_task_runner.update_state_json(
                    "C-14: cc-haha WS task runner MVP",
                    "run-2",
                    stop_rule={
                        "code": "NONE",
                        "stop": False,
                        "reason": "no stop rule triggered",
                    },
                )

            state = json.loads(state_file.read_text(encoding="utf-8"))

        self.assertEqual(state["supervised_completed_tasks"], ["task one"])


class PermissionDecisionTests(unittest.TestCase):
    def test_decide_permission_allows_project_root_read(self):
        allowed, reason = ws_task_runner.decide_permission(
            "Read",
            {"file_path": str(ws_task_runner.PROJECT_ROOT / "AGENTS.md")},
        )

        self.assertTrue(allowed)
        self.assertIn("within project root", reason)

    def test_decide_permission_denies_read_outside_project_root(self):
        allowed, reason = ws_task_runner.decide_permission(
            "Read",
            {"file_path": str(ws_task_runner.PROJECT_ROOT.parent / "outside.txt")},
        )

        self.assertFalse(allowed)
        self.assertIn("outside project root", reason)

    def test_decide_permission_denies_read_without_path(self):
        allowed, reason = ws_task_runner.decide_permission("Read", {})

        self.assertFalse(allowed)
        self.assertIn("missing path field", reason)

    def test_decide_permission_denies_malformed_read_input(self):
        allowed, reason = ws_task_runner.decide_permission("Read", None)

        self.assertFalse(allowed)
        self.assertIn("invalid tool input", reason)

    def test_decide_permission_denies_write_tools(self):
        allowed, reason = ws_task_runner.decide_permission(
            "Write",
            {"file_path": str(ws_task_runner.PROJECT_ROOT / "probe.txt")},
        )

        self.assertFalse(allowed)
        self.assertIn("risk pattern", reason)

    def test_decide_permission_denies_bash_tools(self):
        allowed, reason = ws_task_runner.decide_permission(
            "Bash",
            {"command": "echo hello"},
        )

        self.assertFalse(allowed)
        self.assertIn("risk pattern", reason)


class StopRuleTests(unittest.TestCase):
    def test_classify_stop_rule_returns_none_for_success(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": True},
            {"ok": True, "work_dir": str(ws_task_runner.PROJECT_ROOT)},
            {"ok": True, "error": None, "permission_requests": []},
        )

        self.assertEqual(rule["code"], "NONE")
        self.assertFalse(rule["stop"])

    def test_classify_stop_rule_detects_sidecar_unavailable(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": False, "error": "not found"},
            {"ok": False},
            {"ok": False},
        )

        self.assertEqual(rule["code"], "SIDECAR_UNAVAILABLE")
        self.assertTrue(rule["stop"])

    def test_classify_stop_rule_detects_session_creation_failed(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": True},
            {"ok": False, "error": "HTTP 500"},
            {"ok": False},
        )

        self.assertEqual(rule["code"], "SESSION_CREATE_FAILED")
        self.assertTrue(rule["stop"])

    def test_classify_stop_rule_detects_cwd_drift(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": True},
            {"ok": True, "work_dir": str(ws_task_runner.PROJECT_ROOT.parent)},
            {"ok": False},
        )

        self.assertEqual(rule["code"], "CWD_DRIFT")
        self.assertTrue(rule["stop"])

    def test_classify_stop_rule_detects_ws_timeout(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": True},
            {"ok": True, "work_dir": str(ws_task_runner.PROJECT_ROOT)},
            {"ok": False, "error": "超时 (120s)", "permission_requests": []},
        )

        self.assertEqual(rule["code"], "WS_TIMEOUT")
        self.assertTrue(rule["stop"])

    def test_classify_stop_rule_detects_denied_permission(self):
        rule = ws_task_runner.classify_stop_rule(
            {"found": True},
            {"ok": True, "work_dir": str(ws_task_runner.PROJECT_ROOT)},
            {
                "ok": True,
                "error": None,
                "permission_requests": [
                    {"toolName": "Bash", "allowed": False, "reason": "risk"}
                ],
            },
        )

        self.assertEqual(rule["code"], "PERMISSION_DENIED")
        self.assertTrue(rule["stop"])


class WriteClaudeResultTests(unittest.TestCase):
    def test_write_claude_result_summary_mentions_denied_permissions_on_completed_session(self):
        sidecar_info = {
            "found": True,
            "url": "http://127.0.0.1:8889",
            "source": "test",
        }
        session_info = {
            "ok": True,
            "session_id": "session-1",
        }
        session_result = {
            "ok": True,
            "session_id": "session-1",
            "permission_requests": [
                {
                    "requestId": "req-1",
                    "toolName": "Write",
                    "input": {},
                    "description": "",
                    "allowed": False,
                    "reason": "tool 'Write' matches risk pattern 'write'",
                }
            ],
            "events": [],
            "thinking_count": 0,
            "output_text": "",
            "usage": {},
            "error": None,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            ws_task_runner.write_claude_result(
                sidecar_info,
                session_result,
                "test task",
                session_info,
                elapsed=1.0,
                run_dir=run_dir,
            )

            content = (run_dir / "claude_result.md").read_text(encoding="utf-8")

        self.assertIn("completed with 1 permission(s) denied", content)

    def test_write_claude_result_includes_stop_rule(self):
        sidecar_info = {
            "found": True,
            "url": "http://127.0.0.1:8889",
            "source": "test",
        }
        session_info = {
            "ok": True,
            "session_id": "session-1",
            "work_dir": str(ws_task_runner.PROJECT_ROOT),
        }
        session_result = {
            "ok": False,
            "session_id": "session-1",
            "permission_requests": [],
            "events": [],
            "thinking_count": 0,
            "output_text": "",
            "usage": {},
            "error": "超时 (120s)",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            ws_task_runner.write_claude_result(
                sidecar_info,
                session_result,
                "test task",
                session_info,
                elapsed=120.0,
                run_dir=run_dir,
            )

            content = (run_dir / "claude_result.md").read_text(encoding="utf-8")

        self.assertIn("## Stop Rule", content)
        self.assertIn("WS_TIMEOUT", content)


if __name__ == "__main__":
    unittest.main()
