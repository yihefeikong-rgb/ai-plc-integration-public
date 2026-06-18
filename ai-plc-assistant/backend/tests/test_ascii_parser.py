"""ASCII-LAD-V2 Parser 测试"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generator.ascii_parser import parse_ascii_lad, parse_ascii_lad_with_warnings, extract_elements
from generator.ladder_model import (
    LadderProgram, Network, Rung, Variable,
    Contact, Coil, Timer, Counter, Move, Comparator, BlockCall, Branch,
)


EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "examples")


def _read_example(name: str) -> str:
    path = os.path.join(EXAMPLES_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ── 版本头 ──

class TestHeader:
    def test_parses_version(self):
        prog = parse_ascii_lad("ASCII-LAD-V2\n")
        assert prog.version == "ASCII-LAD-V2"

    def test_missing_header_warns(self):
        prog, warnings = parse_ascii_lad_with_warnings("Network 1\n|----[ A ]----( B )\n")
        assert len(warnings) >= 1


# ── 变量表 ──

class TestVariables:
    def test_parse_three_fields(self):
        text = "ASCII-LAD-V2\n\nVariables:\nI0.0 bStart BOOL\n"
        prog = parse_ascii_lad(text)
        assert len(prog.variables) == 1
        v = prog.variables[0]
        assert v.address == "I0.0"
        assert v.name == "bStart"
        assert v.datatype == "BOOL"
        assert v.comment == ""

    def test_parse_four_fields_with_comment(self):
        text = "ASCII-LAD-V2\n\nVariables:\nI0.0 bStart BOOL 启动按钮\n"
        prog = parse_ascii_lad(text)
        assert prog.variables[0].comment == "启动按钮"

    def test_multiple_variables(self):
        text = _read_example("motor_control.lad")
        prog = parse_ascii_lad(text)
        assert len(prog.variables) == 3
        names = [v.name for v in prog.variables]
        assert names == ["bStart", "bStop", "qMotor"]


# ── 元素提取 ──

class TestExtractElements:
    def test_contact_no(self):
        elems = extract_elements("[ bStart ]")
        assert len(elems) == 1
        assert isinstance(elems[0], Contact)
        assert elems[0].name == "bStart"
        assert elems[0].normally_closed is False

    def test_contact_nc(self):
        elems = extract_elements("[/ bStop ]")
        assert len(elems) == 1
        assert isinstance(elems[0], Contact)
        assert elems[0].normally_closed is True

    def test_coil_normal(self):
        elems = extract_elements("( qMotor )")
        assert len(elems) == 1
        assert isinstance(elems[0], Coil)
        assert elems[0].kind == "normal"

    def test_coil_set(self):
        elems = extract_elements("(S qLatch)")
        assert len(elems) == 1
        assert isinstance(elems[0], Coil)
        assert elems[0].kind == "set"

    def test_coil_reset(self):
        elems = extract_elements("(R qLatch)")
        assert len(elems) == 1
        assert isinstance(elems[0], Coil)
        assert elems[0].kind == "reset"

    def test_timer_ton(self):
        elems = extract_elements("[TON T1 PT=5s]")
        assert len(elems) == 1
        assert isinstance(elems[0], Timer)
        assert elems[0].timer_type == "TON"
        assert elems[0].name == "T1"
        assert elems[0].pt == "5s"

    def test_timer_tof(self):
        elems = extract_elements("[TOF T2 PT=3s]")
        assert isinstance(elems[0], Timer)
        assert elems[0].timer_type == "TOF"

    def test_timer_tp(self):
        elems = extract_elements("[TP T3 PT=1s]")
        assert isinstance(elems[0], Timer)
        assert elems[0].timer_type == "TP"

    def test_counter_ctu(self):
        elems = extract_elements("[CTU C1 PT=10]")
        # wait, the spec says PV= not PT= for counters
        # let me check... yes, CTU uses PV
        pass

    def test_counter_ctu_pv(self):
        elems = extract_elements("[CTU C1 PV=10]")
        assert len(elems) == 1
        assert isinstance(elems[0], Counter)
        assert elems[0].counter_type == "CTU"
        assert elems[0].pv == 10

    def test_counter_ctd(self):
        elems = extract_elements("[CTD C1 PV=5]")
        assert isinstance(elems[0], Counter)
        assert elems[0].counter_type == "CTD"

    def test_move_v21(self):
        """V2.1 格式: [MOVE IN=src OUT=dst]"""
        elems = extract_elements("[MOVE IN=Speed OUT=MotorSpeed]")
        assert len(elems) == 1
        assert isinstance(elems[0], Move)
        assert elems[0].source == "Speed"
        assert elems[0].target == "MotorSpeed"

    def test_move_v20_compat(self):
        """V2.0 兼容: [MOVE src -> dst]"""
        elems = extract_elements("[MOVE Speed -> MotorSpeed]")
        assert len(elems) == 1
        assert isinstance(elems[0], Move)
        assert elems[0].source == "Speed"

    def test_move_literal(self):
        """MOVE 立即数"""
        elems = extract_elements("[MOVE IN=0 OUT=wCounterCV]")
        assert isinstance(elems[0], Move)
        assert elems[0].source == "0"
        assert elems[0].target == "wCounterCV"

    def test_comparator(self):
        elems = extract_elements("[CMP GT iCounter 10]")
        assert len(elems) == 1
        assert isinstance(elems[0], Comparator)
        assert elems[0].op == "GT"
        assert elems[0].a == "iCounter"
        assert elems[0].b == "10"

    def test_fb_call(self):
        elems = extract_elements("[FB MotorCtrl]")
        assert isinstance(elems[0], BlockCall)
        assert elems[0].block_type == "FB"

    def test_fc_call(self):
        elems = extract_elements("[FC Calculate]")
        assert isinstance(elems[0], BlockCall)
        assert elems[0].block_type == "FC"

    def test_series_elements(self):
        elems = extract_elements("|----[ bStart ]----[/ bStop ]----( qMotor )")
        assert len(elems) == 3
        assert isinstance(elems[0], Contact)
        assert isinstance(elems[1], Contact)
        assert elems[1].normally_closed is True
        assert isinstance(elems[2], Coil)


# ── Branch 解析 ──

class TestBranch:
    def test_simple_branch(self):
        text = _read_example("motor_control.lad")
        prog = parse_ascii_lad(text)
        rung = prog.networks[0].rungs[0]
        assert len(rung.elements) == 2
        branch = rung.elements[0]
        coil = rung.elements[1]
        assert isinstance(branch, Branch)
        assert isinstance(coil, Coil)
        assert len(branch.paths) == 2
        # Main path: [bStart, /bStop]
        assert len(branch.paths[0]) == 2
        assert branch.paths[0][0].name == "bStart"
        assert branch.paths[0][1].normally_closed is True
        # Branch path: [qMotor]
        assert len(branch.paths[1]) == 1
        assert branch.paths[1][0].name == "qMotor"

    def test_no_branch_simple_series(self):
        text = "ASCII-LAD-V2\n\nNetwork 1\n|----[ A ]----( B )\n"
        prog = parse_ascii_lad(text)
        rung = prog.networks[0].rungs[0]
        assert len(rung.elements) == 2
        assert isinstance(rung.elements[0], Contact)
        assert isinstance(rung.elements[1], Coil)


# ── Network 结构 ──

class TestNetwork:
    def test_title(self):
        text = _read_example("motor_control.lad")
        prog = parse_ascii_lad(text)
        assert prog.networks[0].title == "电机启动自锁"

    def test_comment(self):
        text = _read_example("motor_control.lad")
        prog = parse_ascii_lad(text)
        assert "自锁" in prog.networks[0].comment

    def test_multiple_networks(self):
        text = _read_example("conveyor.lad")
        prog = parse_ascii_lad(text)
        assert len(prog.networks) == 2
        assert prog.networks[0].number == 1
        assert prog.networks[1].number == 2


# ── Golden Examples 回归测试 ──

class TestGoldenExamples:
    """对每个 .lad 文件验证基本结构完整性"""

    @pytest.fixture(params=[
        ("motor_control.lad", 3, 1),
        ("motor_fwd_rev.lad", 6, 2),
        ("conveyor.lad", 7, 2),
        ("traffic_light.lad", 11, 5),
        ("star_delta.lad", 8, 5),
        ("counter_batch.lad", 6, 3),
        ("timer_demo.lad", 9, 3),
    ])
    def golden(self, request):
        fname, expected_vars, expected_nets = request.param
        text = _read_example(fname)
        prog, warnings = parse_ascii_lad_with_warnings(text)
        return fname, prog, warnings, expected_vars, expected_nets

    def test_no_warnings(self, golden):
        fname, prog, warnings, _, _ = golden
        assert warnings == [], f"{fname}: {warnings}"

    def test_version(self, golden):
        _, prog, _, _, _ = golden
        assert prog.version == "ASCII-LAD-V2"

    def test_variable_count(self, golden):
        fname, prog, _, expected_vars, _ = golden
        assert len(prog.variables) == expected_vars, f"{fname}: got {len(prog.variables)}"

    def test_network_count(self, golden):
        fname, prog, _, _, expected_nets = golden
        assert len(prog.networks) == expected_nets, f"{fname}: got {len(prog.networks)}"

    def test_all_networks_have_rungs(self, golden):
        fname, prog, _, _, _ = golden
        for net in prog.networks:
            assert len(net.rungs) > 0, f"{fname} Network {net.number}: no rungs"


# ── Timer/Counter 特定测试 ──

class TestTimerCounter:
    def test_timer_demo_all_types(self):
        text = _read_example("timer_demo.lad")
        prog = parse_ascii_lad(text)
        timers = []
        for n in prog.networks:
            for r in n.rungs:
                for e in r.elements:
                    if isinstance(e, Timer):
                        timers.append(e)
        types = [t.timer_type for t in timers]
        assert "TON" in types
        assert "TOF" in types
        assert "TP" in types

    def test_counter_batch(self):
        text = _read_example("counter_batch.lad")
        prog = parse_ascii_lad(text)
        counters = []
        for n in prog.networks:
            for r in n.rungs:
                for e in r.elements:
                    if isinstance(e, Counter):
                        counters.append(e)
        assert len(counters) == 1
        assert counters[0].counter_type == "CTU"
        assert counters[0].pv == 12
