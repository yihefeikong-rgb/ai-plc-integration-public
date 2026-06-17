"""测试 generator/export_generator.py — 导出格式生成"""

import csv
import io
import json

from generator import LadderProgram
from generator.export_generator import (
    generate_tag_csv,
    generate_hmi_tags,
    generate_alarm_list,
    generate_variable_json,
)


def _make_program():
    p = LadderProgram("AlarmTest", "报警测试")
    p.add_variable("I0.0", "bStart", "Bool", "启动按钮")
    p.add_variable("I0.1", "bEmergency", "Bool", "急停")
    p.add_variable("I0.2", "bOverload", "Bool", "过载保护")
    p.add_variable("Q0.0", "qMotor", "Bool", "电机输出")
    p.add_variable("M0.0", "mAlarm", "Bool", "报警标志")
    p.add_variable("MW10", "rSpeed", "Real", "速度值")
    return p


class TestTagCSV:
    def test_csv_header(self):
        csv_str = generate_tag_csv(_make_program())
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert "Name" in header
        assert "Data Type" in header
        assert "Logical Address" in header

    def test_csv_rows(self):
        csv_str = generate_tag_csv(_make_program())
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        # header + 6 variables
        assert len(rows) == 7

    def test_address_format(self):
        csv_str = generate_tag_csv(_make_program())
        assert "%I0.0" in csv_str
        assert "%Q0.0" in csv_str


class TestHMITags:
    def test_hmi_prefix(self):
        csv_str = generate_hmi_tags(_make_program(), hmi_prefix="HMI_")
        assert "HMI_bStart" in csv_str
        assert "HMI_qMotor" in csv_str

    def test_access_rights(self):
        csv_str = generate_hmi_tags(_make_program())
        # Q 区和 M 区应该是 Read/Write
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        for row in rows[1:]:
            if row[0].endswith("qMotor") or row[0].endswith("mAlarm"):
                assert row[5] == "Read/Write"
            elif row[0].endswith("bStart"):
                assert row[5] == "Read"

    def test_acquisition_cycle(self):
        csv_str = generate_hmi_tags(_make_program())
        # Real 类型应为 100ms
        assert "100ms" in csv_str


class TestAlarmList:
    def test_alarm_detection(self):
        csv_str = generate_alarm_list(_make_program())
        # bEmergency 和 bOverload 应被识别为报警
        assert "bEmergency" in csv_str or "急停" in csv_str
        assert "bOverload" in csv_str or "过载" in csv_str

    def test_emergency_priority(self):
        csv_str = generate_alarm_list(_make_program())
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        for row in rows[1:]:
            if "Emergency" in row:
                assert row[5] == "1"  # priority

    def test_non_alarm_excluded(self):
        csv_str = generate_alarm_list(_make_program())
        assert "bStart" not in csv_str  # 启动按钮不是报警


class TestVariableJSON:
    def test_valid_json(self):
        json_str = generate_variable_json(_make_program())
        data = json.loads(json_str)
        assert "title" in data
        assert "variables" in data
        assert "summary" in data

    def test_summary_counts(self):
        json_str = generate_variable_json(_make_program())
        data = json.loads(json_str)
        s = data["summary"]
        assert s["total"] == 6
        assert s["inputs"] == 3  # I0.0, I0.1, I0.2
        assert s["outputs"] == 1  # Q0.0

    def test_variable_structure(self):
        json_str = generate_variable_json(_make_program())
        data = json.loads(json_str)
        v = data["variables"][0]
        assert "address" in v
        assert "name" in v
        assert "data_type" in v
        assert "comment" in v

    def test_empty_program(self):
        p = LadderProgram("Empty", "")
        json_str = generate_variable_json(p)
        data = json.loads(json_str)
        assert data["summary"]["total"] == 0
