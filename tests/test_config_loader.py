import json
import os
import sys
import tempfile
import pytest
from pathlib import Path

PROJECT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT / "mcp-servers" / "tia-mcp"))

from config_loader import (
    _resolve_env,
    _looks_like_path,
    _basic_validate,
    validate_ladder_spec,
)


class TestResolveEnv:
    def test_simple_var(self):
        env = {"KEY": "value"}
        assert _resolve_env("${KEY}", env) == "value"

    def test_var_with_default(self):
        env = {}
        assert _resolve_env("${MISSING:default_val}", env) == "default_val"

    def test_var_uses_env_over_default(self):
        env = {"KEY": "real"}
        assert _resolve_env("${KEY:fallback}", env) == "real"

    def test_no_placeholders(self):
        assert _resolve_env("plain/text", {}) == "plain/text"

    def test_multiple_vars(self):
        env = {"HOST": "127.0.0.1", "PORT": "8080"}
        result = _resolve_env("${HOST}:${PORT}", env)
        assert result == "127.0.0.1:8080"

    def test_os_environ_fallback(self, monkeypatch):
        monkeypatch.setenv("FALLBACK_TEST", "from_os")
        assert _resolve_env("${FALLBACK_TEST:nope}", {}) == "from_os"


class TestLooksLikePath:
    def test_url_not_path(self):
        assert not _looks_like_path("api_url", "https://api.example.com")
        assert not _looks_like_path("endpoint", "http://localhost:8080")
        assert not _looks_like_path("addr", "tcp://0.0.0.0:4840")

    def test_path_keys(self):
        assert _looks_like_path("project_path", "./my_project")
        assert _looks_like_path("dll_path", "./bin/CartGen.dll")
        assert _looks_like_path("output_dir", "./output")
        assert _looks_like_path("templates_dir", "templates")

    def test_non_path_keys(self):
        assert not _looks_like_path("timeout", "30")
        assert not _looks_like_path("api_key", "sk-abc123")
        assert not _looks_like_path(
            "device_name", "S7-1500/ET200MP station_1"
        )

    def test_file_extensions(self):
        assert _looks_like_path("anything", "config.yaml")
        assert _looks_like_path("anything", "project.ap18")

    def test_path_separators(self):
        assert _looks_like_path("anything", "subdir/file.txt")
        assert _looks_like_path("anything", r"dir\sub\file.txt")


# 符合 schema 的完整 spec（含 address 字段）
MINIMAL_SPEC = {
    "blockName": "TestBlock",
    "blockNumber": 100,
    "interface": {
        "inputs": [{"name": "iStart", "type": "Bool", "address": "%I0.0", "comment": "start"}],
        "outputs": [{"name": "oRun", "type": "Bool", "address": "%Q0.0", "comment": "run"}],
    },
    "networks": [
        {
            "title": "Test",
            "elements": [
                {"type": "normally_open", "operand": "iStart"},
                {"type": "coil", "operand": "oRun"},
            ],
        }
    ],
}


class TestLadderSpecValidation:
    def test_valid_spec_passes(self):
        result = validate_ladder_spec(MINIMAL_SPEC)
        assert result["valid"], f"Should pass: {result}"

    def test_missing_block_name(self):
        spec = {**MINIMAL_SPEC}
        del spec["blockName"]
        r = validate_ladder_spec(spec)
        assert not r["valid"]

    def test_missing_networks(self):
        spec = {**MINIMAL_SPEC}
        del spec["networks"]
        r = validate_ladder_spec(spec)
        assert not r["valid"]

    def test_empty_networks(self):
        spec = {**MINIMAL_SPEC, "networks": []}
        r = validate_ladder_spec(spec)
        assert not r["valid"]

    def test_non_dict_root(self):
        r = validate_ladder_spec("not a dict")
        assert not r["valid"]

    def test_missing_operand(self):
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["networks"][0]["elements"].append({"type": "coil"})
        r = validate_ladder_spec(spec)
        assert not r["valid"]

    def test_valid_element_types(self):
        for t in ("normally_open", "normally_closed", "coil", "coil_set", "coil_reset"):
            spec = json.loads(json.dumps(MINIMAL_SPEC))
            spec["networks"][0]["elements"] = [{"type": t, "operand": "oTest"}]
            r = validate_ladder_spec(spec)
            assert r["valid"], f"Type '{t}' should be valid but got: {r}"


class TestBasicValidate:
    def test_interface_missing_inputs_full_schema(self):
        """完整 schema 校验能检测到 interface 缺少 inputs"""
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        del spec["interface"]["inputs"]
        r = validate_ladder_spec(spec)
        assert not r["valid"]

    def test_network_not_object(self):
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["networks"] = ["string"]
        r = _basic_validate(spec)
        assert r

    def test_element_not_object(self):
        spec = json.loads(json.dumps(MINIMAL_SPEC))
        spec["networks"][0]["elements"] = ["not an object"]
        r = _basic_validate(spec)
        assert r

    def test_minimal_valid(self):
        r = _basic_validate(MINIMAL_SPEC)
        assert r == []
