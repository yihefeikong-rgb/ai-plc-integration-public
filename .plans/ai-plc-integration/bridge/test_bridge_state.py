import json
import sys
import tempfile
import unittest
from pathlib import Path


BRIDGE_DIR = Path(__file__).resolve().parent
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from bridge_state import BridgeStateError, locked_state


class BridgeStateTests(unittest.TestCase):
    def test_locked_state_persists_one_atomic_update_and_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            state_file.write_text('{"stage":"NEED_CODEX_REVIEW"}', encoding="utf-8")

            with locked_state(state_file) as state:
                state["review_status"] = "PENDING"

            persisted = json.loads(state_file.read_text(encoding="utf-8"))
            lock_file = state_file.with_name("state.json.lock")

        self.assertEqual(persisted["review_status"], "PENDING")
        self.assertFalse(lock_file.exists())

    def test_locked_state_rejects_existing_lock_without_overwriting_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "state.json"
            original = '{"stage":"NEED_CODEX_REVIEW"}'
            state_file.write_text(original, encoding="utf-8")
            state_file.with_name("state.json.lock").write_text("other runner", encoding="utf-8")

            with self.assertRaises(BridgeStateError):
                with locked_state(state_file) as state:
                    state["review_status"] = "PENDING"

            persisted = state_file.read_text(encoding="utf-8")

        self.assertEqual(persisted, original)


if __name__ == "__main__":
    unittest.main()
