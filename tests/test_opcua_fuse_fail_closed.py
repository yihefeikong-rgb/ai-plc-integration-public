"""opcua_safety 熔断状态文件的 fail-closed 与原子写测试。"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


def _load_opcua_safety():
    """按 opcua-mcp/server.py 的方式用 spec 加载，不污染 sys.path。"""
    spec = importlib.util.spec_from_file_location(
        "opcua_safety_fuse_test", PROJECT_ROOT / "mcp-servers" / "opcua-mcp" / "opcua_safety.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["opcua_safety_fuse_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def safety(tmp_path, monkeypatch):
    module = _load_opcua_safety()
    state_file = tmp_path / "opcua_fuse_state.json"
    monkeypatch.setattr(module, "FUSE_STATE_FILE", state_file)
    # 每个测试前恢复内存默认状态
    module.FUSE_STATE.update({
        "tripped": False,
        "consecutive_errors": 0,
        "max_errors": 3,
        "trip_reason": "",
        "trip_time": None,
    })
    return module


class TestLoadFuseStateFailClosed:
    def test_missing_file_is_normal_first_start(self, safety):
        safety._load_fuse_state()
        assert safety.FUSE_STATE["tripped"] is False

    def test_corrupted_json_trips_fuse(self, safety):
        safety.FUSE_STATE_FILE.write_text("{ not valid json", encoding="utf-8")
        safety._load_fuse_state()
        assert safety.FUSE_STATE["tripped"] is True
        assert "损坏" in safety.FUSE_STATE["trip_reason"]

    def test_non_dict_json_trips_fuse(self, safety):
        safety.FUSE_STATE_FILE.write_text('["tripped": false]', encoding="utf-8")
        safety._load_fuse_state()
        assert safety.FUSE_STATE["tripped"] is True

    def test_valid_state_is_restored(self, safety):
        safety.FUSE_STATE_FILE.write_text(
            json.dumps({"tripped": False, "consecutive_errors": 1,
                        "max_errors": 3, "trip_reason": "", "trip_time": None}),
            encoding="utf-8",
        )
        safety._load_fuse_state()
        assert safety.FUSE_STATE["tripped"] is False
        assert safety.FUSE_STATE["consecutive_errors"] == 1


class TestSaveFuseStateAtomic:
    def test_save_writes_valid_json_without_tmp_residue(self, safety):
        safety.FUSE_STATE["tripped"] = True
        safety.FUSE_STATE["trip_reason"] = "test"
        safety._save_fuse_state()
        data = json.loads(safety.FUSE_STATE_FILE.read_text(encoding="utf-8"))
        assert data["tripped"] is True
        assert not list(safety.FUSE_STATE_FILE.parent.glob("*.tmp"))

    def test_save_failure_leaves_old_file_intact(self, safety, monkeypatch):
        safety.FUSE_STATE["tripped"] = True
        safety._save_fuse_state()
        old = safety.FUSE_STATE_FILE.read_text(encoding="utf-8")

        def broken_write(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(safety.Path, "write_text", broken_write)
        safety.FUSE_STATE["tripped"] = False
        safety._save_fuse_state()
        # 写失败时旧状态文件保持完整（不被半写破坏）
        assert json.loads(safety.FUSE_STATE_FILE.read_text(encoding="utf-8"))["tripped"] is True
        assert old
