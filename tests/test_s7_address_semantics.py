"""S7 原始地址到安全语义的离线契约测试。"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


PROJECT_ROOT = Path(__file__).parent.parent
BRIDGE_DIR = PROJECT_ROOT / "mcp-servers" / "plc-mcp-bridge"
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))


def test_only_explicitly_mapped_s7_addresses_are_writable():
    from safety.validator import WriteValidator

    validator = WriteValidator()

    assert validator.resolve_s7_write_address("MW14") == {
        "target": "DB1.MotorSpeed",
        "type": "int16",
    }
    assert validator.resolve_s7_write_address("MW10") is None
    assert validator.resolve_s7_write_address("M1.2") is None


@pytest.mark.parametrize(
    ("address", "value", "expected"),
    [
        ("M0.1", True, True),
        ("M0.1", "true", True),
        ("M0.1", "false", False),
        ("MW14", "3000", 3000),
        ("MD20", "3.5", 3.5),
    ],
)
def test_strict_s7_value_conversion_accepts_only_declared_formats(address, value, expected):
    from s7_adapter import S7Adapter

    assert S7Adapter.parse_write_value(address, value) == expected


@pytest.mark.parametrize(
    ("address", "value"),
    [
        ("M0.1", "yes"),
        ("M0.1", "1"),
        ("M0.1", 1),
        ("MW14", "3.5"),
        ("MW14", "32768"),
        ("MW14", "nan"),
        ("MD20", "NaN"),
        ("MD20", "Infinity"),
        ("MD20", float("inf")),
    ],
)
def test_strict_s7_value_conversion_rejects_ambiguous_and_non_finite_values(address, value):
    from s7_adapter import S7Adapter

    with pytest.raises(ValueError):
        S7Adapter.parse_write_value(address, value)


def test_s7_write_rejects_unmapped_address_before_read_or_write(monkeypatch):
    import tools_s7

    mock_adapter = MagicMock()
    monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)
    monkeypatch.setattr(tools_s7, "adapter", mock_adapter)
    monkeypatch.setattr(tools_s7, "_audit", MagicMock())

    result = asyncio.run(tools_s7.s7_write("MW10", "100"))

    assert "未映射" in result
    mock_adapter.read_address.assert_not_called()
    mock_adapter.write_address.assert_not_called()


def test_s7_write_validates_mapped_semantic_target_and_normalized_value(monkeypatch):
    import tools_s7

    mock_adapter = MagicMock()
    mock_adapter.parse_write_value.return_value = 100
    mock_adapter.read_address.return_value = 50
    mock_adapter.write_address.return_value = "✅ 写入成功"
    mock_validator = MagicMock()
    mock_validator.resolve_s7_write_address.return_value = {
        "target": "DB1.MotorSpeed",
        "type": "int16",
    }
    mock_validator.validate.return_value = MagicMock(
        allowed=True,
        needs_confirmation=False,
        reason="OK",
    )

    monkeypatch.setattr(tools_s7, "SAFETY_AVAILABLE", True)
    monkeypatch.setattr(tools_s7, "adapter", mock_adapter)
    monkeypatch.setattr(tools_s7, "safety_val", mock_validator)
    monkeypatch.setattr(
        tools_s7,
        "shadow_sim",
        MagicMock(simulate_write=AsyncMock(return_value=MagicMock(safe=True))),
    )
    monkeypatch.setattr(tools_s7, "_audit", MagicMock())

    result = asyncio.run(tools_s7.s7_write("MW14", "100"))

    assert "写入成功" in result
    mock_validator.validate.assert_called_once_with(
        "DB1.MotorSpeed", 100, current_value=50,
    )
    mock_adapter.write_address.assert_called_once_with("MW14", 100)
