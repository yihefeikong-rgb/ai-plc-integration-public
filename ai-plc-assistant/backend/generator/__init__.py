"""PLC 代码生成器 — 梯形图/SCL 代码结构化输出"""

import re
from typing import List, Optional


class Network:
    """单个 Network 块"""
    def __init__(self, number: int, title: str = "", code: str = "", comment: str = ""):
        self.number = number
        self.title = title
        self.code = code
        self.comment = comment

    def to_text(self) -> str:
        lines = [f"Network {self.number}: {self.title}"]
        if self.comment:
            lines.append(f"// {self.comment}")
        if self.code:
            lines.append(self.code)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "code": self.code,
            "comment": self.comment,
        }


class Variable:
    """变量定义"""
    def __init__(self, address: str, name: str, data_type: str, comment: str = ""):
        self.address = address
        self.name = name
        self.data_type = data_type
        self.comment = comment

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "name": self.name,
            "data_type": self.data_type,
            "comment": self.comment,
        }


class LadderProgram:
    """梯形图程序：包含变量表和网络列表"""
    def __init__(self, title: str = "", description: str = ""):
        self.title = title
        self.description = description
        self.variables: List[Variable] = []
        self.networks: List[Network] = []

    def add_variable(self, address: str, name: str, data_type: str = "Bool", comment: str = ""):
        self.variables.append(Variable(address, name, data_type, comment))

    def add_network(self, number: int, title: str = "", code: str = "", comment: str = ""):
        self.networks.append(Network(number, title, code, comment))

    def to_text(self) -> str:
        parts = [f"# {self.title}", ""]
        if self.description:
            parts.append(f"> {self.description}")
            parts.append("")

        # 变量表
        if self.variables:
            parts.append("## 变量表")
            parts.append("| 地址 | 符号 | 类型 | 注释 |")
            parts.append("|------|------|------|------|")
            for v in self.variables:
                parts.append(f"| {v.address} | {v.name} | {v.data_type} | {v.comment} |")
            parts.append("")

        # 网络
        for n in self.networks:
            parts.append(f"## Network {n.number}: {n.title}")
            if n.comment:
                parts.append(f"// {n.comment}")
            if n.code:
                parts.append("```")
                parts.append(n.code)
                parts.append("```")
            parts.append("")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "variables": [v.to_dict() for v in self.variables],
            "networks": [n.to_dict() for n in self.networks],
        }


def parse_raw_output(text: str) -> LadderProgram:
    """从原始文本（LLM 输出或模板输出）中解析出结构化的 LadderProgram"""
    program = LadderProgram()

    # 提取标题
    title_match = re.search(r'#\s*(.+?)[\n\r]', text)
    if title_match:
        program.title = title_match.group(1).strip()

    # 提取描述
    desc_match = re.search(r'>\s*(.+?)[\n\r]', text)
    if desc_match:
        program.description = desc_match.group(1).strip()

    # 提取变量表
    var_section = re.search(
        r'##?\s*变量表.*?\n(.*?)(?=##|\Z)',
        text,
        re.DOTALL,
    )
    if var_section:
        var_text = var_section.group(1)
        var_pattern = re.compile(
            r'\|\s*([\w.%]+)\s*\|\s*(\w+)\s*\|\s*(\w+)\s*\|\s*(.*?)\s*\|'
        )
        # 表头关键词 — 跳过 Markdown 表头行
        header_keywords = {"地址", "符号", "类型", "注释", "address", "name", "type", "comment", "datatype", "data_type"}
        for m in var_pattern.finditer(var_text):
            addr = m.group(1).strip()
            name = m.group(2).strip()
            if addr.lower() in header_keywords or name.lower() in header_keywords:
                continue
            program.add_variable(
                address=addr,
                name=name,
                data_type=m.group(3).strip(),
                comment=m.group(4).strip(),
            )

    # 提取 Network
    network_pattern = re.compile(
        r'##?\s*Network\s*(\d+)[:\s]*(.*?)[\n\r]'
        r'(?://\s*(.*?)[\n\r])?'
        r'```(?:\w+)?\s*(.*?)```',
        re.DOTALL,
    )
    for m in network_pattern.finditer(text):
        num = int(m.group(1))
        title = m.group(2).strip()
        code = m.group(4).strip()
        comment = m.group(3).strip() if m.group(3) else ""
        if not comment and code.startswith("//"):
            first_line = code.split("\n")[0]
            comment = first_line.replace("//", "").strip()
            code = "\n".join(code.split("\n")[1:]).strip()
        program.add_network(num, title, code, comment)

    # 如果正则解析没命中，尝试另一种格式
    if not program.networks:
        network_alt = re.findall(
            r'Network\s*(\d+)[\s:]*([^\n]*)(.*?)(?=Network\s+\d+|\Z)',
            text,
            re.DOTALL,
        )
        for num_str, title, rest in network_alt:
            rest = rest.strip()
            comment = ""
            code = rest
            if rest.startswith("//"):
                nl = rest.find("\n")
                if nl > 0:
                    comment = rest[2:nl].strip()
                    code = rest[nl:].strip()
            program.add_network(int(num_str), title.strip(), code, comment)

    return program


def build_demo_program(template_id: str, variables: dict) -> LadderProgram:
    """基于模板 ID 和变量生成演示梯形图程序"""
    demos = {
        "motor-start-stop": _demo_motor_start_stop,
        "traffic-light": _demo_traffic_light,
        "conveyor": _demo_conveyor,
    }
    builder = demos.get(template_id, _demo_motor_start_stop)
    return builder(variables)


def _demo_motor_start_stop(vars: dict) -> LadderProgram:
    p = LadderProgram("电机启动/停止控制", "使用自锁电路实现电机的启动和停止控制")
    p.add_variable("I0.0", "bStart", "Bool", "启动按钮")
    p.add_variable("I0.1", "bStop", "Bool", "停止按钮")
    p.add_variable("I0.2", "bOverload", "Bool", "过载保护")
    p.add_variable("Q0.0", "qMotor", "Bool", "电机输出")
    p.add_variable("Q0.1", "qAlarm", "Bool", "故障指示")
    p.add_network(1, "启动保持",
        "     bStart         bStop      bOverload      qMotor\n"
        "------| |----+-------|/|--------|/|------------( )--\n"
        "             |\n"
        "             | qMotor\n"
        "             +---| |",
        "按下启动按钮后自锁保持，按停止或过载时断开")
    p.add_network(2, "故障指示",
        "     bOverload        qAlarm\n"
        "------| |--------------( )--",
        "过载时输出故障指示")
    return p


def _demo_traffic_light(vars: dict) -> LadderProgram:
    green_time = vars.get("green_time", "30")
    yellow_time = vars.get("yellow_time", "3")
    p = LadderProgram("十字路口交通灯控制",
        f"东西/南北方向交替通行，绿灯{green_time}s，黄灯{yellow_time}s")
    p.add_variable("I0.0", "bStart", "Bool", "启动按钮")
    p.add_variable("I0.1", "bStop", "Bool", "停止按钮")
    p.add_variable("I0.2", "bEmergency", "Bool", "急停")
    p.add_variable("Q0.0", "qEW_Red", "Bool", "东西红灯")
    p.add_variable("Q0.1", "qEW_Green", "Bool", "东西绿灯")
    p.add_variable("Q0.2", "qEW_Yellow", "Bool", "东西黄灯")
    p.add_variable("Q0.3", "qNS_Red", "Bool", "南北红灯")
    p.add_variable("Q0.4", "qNS_Green", "Bool", "南北绿灯")
    p.add_variable("Q0.5", "qNS_Yellow", "Bool", "南北黄灯")
    p.add_network(1, "启动条件",
        "     bEmergency       bStart          bStop         RUN\n"
        "-------|/|----+--------| |-----+-------|/|---------(S)--\n"
        "             |                 |\n"
        "             |      RUN        |\n"
        "             +------| |--------+",
        "急停未触发且按下启动后RUN置位，按停止复位")
    p.add_network(2, f"东西绿灯 ({green_time}s)",
        "     RUN      T_Green.Q      T_Yellow.Q      EW_Green\n"
        "------| |------|/|------------|/|-------------( )--",
        f"绿灯持续{green_time}秒")
    p.add_network(3, f"东西黄灯 ({yellow_time}s)",
        "     EW_Green    T_Green.Q       EW_Yellow\n"
        "------| |----------| |-----------( )--",
        f"绿灯结束后黄灯持续{yellow_time}秒")
    p.add_network(4, "南北绿灯",
        "     EW_Yellow   T_Yellow.Q      NS_Green\n"
        "------| |-----------| |----------( )--",
        "东西黄灯结束后南北绿灯亮起")
    return p


def _demo_conveyor(vars: dict) -> LadderProgram:
    p = LadderProgram("传送带控制", "带传感器检测的传送带启停与正反转控制")
    p.add_variable("I0.0", "bStart", "Bool", "启动按钮")
    p.add_variable("I0.1", "bStop", "Bool", "停止按钮")
    p.add_variable("I0.2", "sSensorA", "Bool", "传送带A端传感器")
    p.add_variable("I0.3", "sSensorB", "Bool", "传送带B端传感器")
    p.add_variable("Q0.0", "qMotorFwd", "Bool", "正转输出")
    p.add_variable("Q0.1", "qMotorRev", "Bool", "反转输出")
    p.add_network(1, "正转控制",
        "   bStart    bStop   sSensorB     qMotorRev    qMotorFwd\n"
        "----| |------|/|------|/|-----------|/|---------( )--\n"
        "   |\n"
        "   | qMotorFwd\n"
        "   +---| |",
        "B端无料时正转允许")
    p.add_network(2, "反转控制",
        "   sSensorA    sSensorB    qMotorFwd    qMotorRev\n"
        "----| |----------| |---------|/|--------( )--",
        "A端和B端同时有料时反转")
    return p
