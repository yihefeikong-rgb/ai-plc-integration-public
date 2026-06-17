"""变量表 / HMI 变量导出器"""

import csv
import io
import json
from typing import Optional

from generator import LadderProgram, Variable


def generate_tag_csv(program: LadderProgram) -> str:
    """生成 TIA Portal 标签表 CSV（可导入）

    格式: Name,Path,Data Type,Logical Address,Comment,Hmi Visible,Hmi Accessible
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Name", "Path", "Data Type", "Logical Address",
        "Comment", "Hmi Visible", "Hmi Accessible",
    ])

    for v in program.variables:
        writer.writerow([
            v.name,
            "",
            v.data_type,
            _format_address(v.address),
            v.comment,
            "True",
            "True",
        ])

    return output.getvalue()


def generate_hmi_tags(program: LadderProgram, hmi_prefix: str = "HMI_") -> str:
    """生成 HMI 变量映射表 CSV

    格式: HMI Name,PLC Tag,Data Type,Address,Comment,Access,Acquisition Cycle
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "HMI Name", "PLC Tag", "Data Type", "Address",
        "Comment", "Access", "Acquisition Cycle",
    ])

    for v in program.variables:
        # HMI 名称加前缀
        hmi_name = f"{hmi_prefix}{v.name}"
        # 判断读写权限
        access = "Read/Write" if v.address.startswith(("Q", "%Q", "M", "%M")) else "Read"
        # 采集周期
        cycle = "100ms" if v.data_type in ("Real", "Int", "DInt", "Word") else "1s"

        writer.writerow([
            hmi_name,
            v.name,
            v.data_type,
            _format_address(v.address),
            v.comment,
            access,
            cycle,
        ])

    return output.getvalue()


def generate_alarm_list(program: LadderProgram) -> str:
    """从变量中提取可能的报警点，生成报警列表 CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Tag Name", "Trigger Bit", "Alarm Text", "Class", "Priority"])

    alarm_id = 1
    alarm_keywords = ["alarm", "fault", "error", "overload", "emergency", "stop",
                       "报警", "故障", "错误", "过载", "急停"]

    for v in program.variables:
        is_alarm = any(kw in v.name.lower() or kw in v.comment for kw in alarm_keywords)
        if is_alarm and v.data_type == "Bool":
            alarm_class = "Emergency" if any(k in v.comment for k in ("急停", "emergency")) else "Fault"
            priority = 1 if alarm_class == "Emergency" else 5
            writer.writerow([
                alarm_id,
                v.name,
                _format_address(v.address),
                v.comment or v.name,
                alarm_class,
                priority,
            ])
            alarm_id += 1

    return output.getvalue()


def generate_variable_json(program: LadderProgram) -> str:
    """生成变量表 JSON（供前端使用）"""
    data = {
        "title": program.title,
        "variables": [v.to_dict() for v in program.variables],
        "summary": {
            "total": len(program.variables),
            "inputs": len([v for v in program.variables if v.address.startswith(("I", "%I"))]),
            "outputs": len([v for v in program.variables if v.address.startswith(("Q", "%Q"))]),
            "memory": len([v for v in program.variables if v.address.startswith(("M", "%M"))]),
        },
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def _format_address(address: str) -> str:
    """标准化地址格式"""
    addr = address.strip()
    if addr.startswith("%"):
        return addr
    # I0.0 → %I0.0
    if addr and addr[0] in ("I", "Q", "M"):
        return f"%{addr}"
    return addr
