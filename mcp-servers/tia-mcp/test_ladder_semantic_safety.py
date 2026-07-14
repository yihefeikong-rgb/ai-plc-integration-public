"""LadderSpec 结构与语义安全契约的离线测试。"""
from __future__ import annotations

import copy

from config_loader import safety_validate_ladder, validate_ladder_spec


def _variable(name: str, value_type: str, address: str) -> dict:
    return {
        "name": name,
        "type": value_type,
        "address": address,
        "comment": name,
    }


def _guarded_motor_spec() -> dict:
    return {
        "blockName": "MotorForwardReverse",
        "blockNumber": 100,
        "interface": {
            "inputs": [
                _variable("iStart", "Bool", "%I0.0"),
                _variable("iReverse", "Bool", "%I0.1"),
                _variable("iStop", "Bool", "%I0.2"),
                _variable("iOverload", "Bool", "%I0.3"),
            ],
            "outputs": [
                _variable("oRunFwd", "Bool", "%Q0.0"),
                _variable("oRunRev", "Bool", "%Q0.1"),
            ],
        },
        "networks": [
            {
                "title": "正转",
                "elements": [
                    {"type": "normally_closed", "operand": "iStop"},
                    {"type": "normally_closed", "operand": "iOverload"},
                    {"type": "normally_closed", "operand": "oRunRev"},
                    {"type": "normally_open", "operand": "iStart"},
                    {"type": "coil", "operand": "oRunFwd"},
                ],
            },
            {
                "title": "反转",
                "elements": [
                    {"type": "normally_closed", "operand": "iStop"},
                    {"type": "normally_closed", "operand": "iOverload"},
                    {"type": "normally_closed", "operand": "oRunFwd"},
                    {"type": "normally_open", "operand": "iReverse"},
                    {"type": "coil", "operand": "oRunRev"},
                ],
            },
        ],
    }


def _timer_spec() -> dict:
    return {
        "blockName": "DelayBlock",
        "blockNumber": 101,
        "interface": {
            "inputs": [_variable("iStart", "Bool", "%I0.0")],
            "outputs": [_variable("oDone", "Bool", "%Q0.0")],
        },
        "networks": [
            {
                "title": "延时",
                "elements": [
                    {"type": "normally_open", "operand": "iStart"},
                    {"type": "timer_on_delay", "operand": "iStart"},
                    {"type": "coil", "operand": "oDone"},
                ],
            },
        ],
    }


def test_guarded_forward_reverse_motor_passes_semantic_validation():
    result = safety_validate_ladder(_guarded_motor_spec())

    assert result["safe"], result


def test_each_motor_output_network_requires_its_own_estop_contact():
    spec = _guarded_motor_spec()
    spec["networks"][0]["elements"] = [
        element for element in spec["networks"][0]["elements"]
        if element["operand"] != "iStop"
    ]

    result = safety_validate_ladder(spec)

    assert not result["safe"]
    assert any("iStop" in warning for warning in result["warnings"])


def test_forward_reverse_outputs_require_peer_interlock_in_each_network():
    spec = _guarded_motor_spec()
    for network in spec["networks"]:
        network["elements"] = [
            element for element in network["elements"]
            if element["operand"] not in {"oRunFwd", "oRunRev"}
            or element["type"] == "coil"
        ]

    result = safety_validate_ladder(spec)

    assert not result["safe"]
    assert any("互锁" in warning for warning in result["warnings"])


def test_timer_without_instance_or_preset_is_structurally_rejected():
    result = validate_ladder_spec(_timer_spec())

    assert not result["valid"]


def test_cartgen_unsupported_interface_type_is_structurally_rejected():
    spec = copy.deepcopy(_timer_spec())
    spec["interface"]["inputs"][0]["type"] = "DWord"
    spec["networks"][0]["elements"][1].update({
        "timer_instance": "IEC_Timer_0",
        "preset_time": "T#5S",
    })

    result = validate_ladder_spec(spec)

    assert not result["valid"]
