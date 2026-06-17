"""测试 generator/scl_generator.py — SCL 源码生成"""

from generator import LadderProgram
from generator.scl_generator import generate_scl


def _make_program():
    p = LadderProgram("MotorControl", "电机控制 FB")
    p.add_variable("I0.0", "bStart", "Bool", "启动")
    p.add_variable("I0.1", "bStop", "Bool", "停止")
    p.add_variable("Q0.0", "qMotor", "Bool", "电机")
    p.add_variable("M0.0", "mRunning", "Bool", "运行状态")
    p.add_network(1, "启动逻辑", "bStart--| |--( )--qMotor", "自锁电路")
    return p


class TestGenerateSCL:
    def test_fb_output(self):
        scl = generate_scl(_make_program(), "FB")
        assert 'FUNCTION_BLOCK "MotorControl"' in scl
        assert "END_FUNCTION_BLOCK" in scl

    def test_fc_output(self):
        scl = generate_scl(_make_program(), "FC")
        assert 'FUNCTION "MotorControl"' in scl
        assert "END_FUNCTION" in scl

    def test_var_sections(self):
        scl = generate_scl(_make_program())
        assert "VAR_INPUT" in scl
        assert "VAR_OUTPUT" in scl
        assert "bStart" in scl
        assert "qMotor" in scl

    def test_internal_vars(self):
        scl = generate_scl(_make_program())
        # M 区变量应在 VAR 段
        lines = scl.split("\n")
        has_var_section = any("VAR" == line.strip() for line in lines)
        assert has_var_section
        assert "mRunning" in scl

    def test_network_comments(self):
        scl = generate_scl(_make_program())
        assert "Network 1" in scl
        assert "启动逻辑" in scl

    def test_metadata_header(self):
        scl = generate_scl(_make_program())
        assert "TITLE" in scl
        assert "AI PLC Assistant" in scl

    def test_custom_block_name(self):
        scl = generate_scl(_make_program(), "FB", "CustomName")
        assert '"CustomName"' in scl

    def test_empty_program(self):
        p = LadderProgram("Empty", "")
        scl = generate_scl(p)
        assert "FUNCTION_BLOCK" in scl
        assert "END_FUNCTION_BLOCK" in scl
