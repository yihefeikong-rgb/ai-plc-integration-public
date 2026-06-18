"""
LadderModel — ASCII-LAD-V2 的纯数据模型

这是 ASCII 解析器的输出，也是渲染器/导出器的输入。
不是 AST，不含逻辑，只有数据。

数据流：
    ASCII 文本 → ascii_parser.py → LadderProgram (本文件)
    LadderProgram → 前端渲染 / SCL 导出 / XML 导出
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Union


# ═══════════════════════════════════════════════════════════
# 变量
# ═══════════════════════════════════════════════════════════

@dataclass
class Variable:
    """PLC 变量声明"""
    address: str        # I0.0, Q0.0, M0.0, MW10, DB1.DBW0
    name: str           # 匈牙利命名: bStart, qMotor, rSpeed
    datatype: str       # BOOL, INT, REAL, TIME, ...
    comment: str = ""   # 中文注释


# ═══════════════════════════════════════════════════════════
# 梯形图元素
# ═══════════════════════════════════════════════════════════

@dataclass
class Contact:
    """触点"""
    name: str
    normally_closed: bool = False


@dataclass
class Coil:
    """线圈"""
    name: str
    kind: str = "normal"   # "normal" | "set" | "reset"


@dataclass
class Timer:
    """定时器 (TON/TOF/TP)"""
    timer_type: str   # "TON" | "TOF" | "TP"
    name: str         # T1, T2, ...
    pt: str           # "5s", "500ms"


@dataclass
class Counter:
    """计数器 (CTU/CTD)"""
    counter_type: str  # "CTU" | "CTD"
    name: str          # C1, C2, ...
    pv: int            # 预设值


@dataclass
class Move:
    """赋值操作"""
    source: str
    target: str


@dataclass
class Comparator:
    """比较器"""
    op: str    # "EQ" | "NE" | "GT" | "GE" | "LT" | "LE"
    a: str
    b: str


@dataclass
class BlockCall:
    """功能块/函数调用"""
    block_type: str   # "FB" | "FC"
    name: str


# 元素联合类型
Element = Union[Contact, Coil, Timer, Counter, Move, Comparator, BlockCall]


# ═══════════════════════════════════════════════════════════
# 并联分支
# ═══════════════════════════════════════════════════════════

@dataclass
class Branch:
    """并联分支（OR 逻辑）

    paths[0] = 主路径（+ 之前的元素）
    paths[1..n] = 分支路径
    """
    paths: list = field(default_factory=list)  # list[list[Element]]


# ═══════════════════════════════════════════════════════════
# 结构
# ═══════════════════════════════════════════════════════════

@dataclass
class Rung:
    """一个梯级（从左轨到右轨）

    elements 是有序列表，可包含 Element 或 Branch。
    Branch 对象嵌在序列中，表示该位置有并联分支。
    """
    elements: list = field(default_factory=list)  # list[Element | Branch]


@dataclass
class Network:
    """一个网络"""
    number: int
    title: str = ""
    comment: str = ""
    rungs: list = field(default_factory=list)  # list[Rung]


@dataclass
class LadderProgram:
    """完整的梯形图程序"""
    version: str = "ASCII-LAD-V2"
    variables: list = field(default_factory=list)  # list[Variable]
    networks: list = field(default_factory=list)   # list[Network]


# ═══════════════════════════════════════════════════════════
# 序列化（→ JSON dict，供前端消费）
# ═══════════════════════════════════════════════════════════

def _element_to_dict(elem) -> dict:
    """将单个元素转为前端可消费的 dict。"""
    if isinstance(elem, Contact):
        return {"type": "contact", "name": elem.name, "normally_closed": elem.normally_closed}
    if isinstance(elem, Coil):
        return {"type": "coil", "name": elem.name, "kind": elem.kind}
    if isinstance(elem, Timer):
        return {"type": "timer", "timer_type": elem.timer_type, "name": elem.name, "pt": elem.pt}
    if isinstance(elem, Counter):
        return {"type": "counter", "counter_type": elem.counter_type, "name": elem.name, "pv": elem.pv}
    if isinstance(elem, Move):
        return {"type": "move", "source": elem.source, "target": elem.target}
    if isinstance(elem, Comparator):
        return {"type": "comparator", "op": elem.op, "a": elem.a, "b": elem.b}
    if isinstance(elem, BlockCall):
        return {"type": "block_call", "block_type": elem.block_type, "name": elem.name}
    if isinstance(elem, Branch):
        return {
            "type": "branch",
            "paths": [[_element_to_dict(e) for e in path] for path in elem.paths],
        }
    return {"type": "unknown"}


def program_to_dict(prog: LadderProgram) -> dict:
    """将 LadderProgram 序列化为前端可消费的 dict。

    输出格式与旧 generator/__init__.py 的 LadderProgram.to_dict() 兼容，
    同时新增 rungs 字段携带结构化元素数据。
    """
    variables = []
    for v in prog.variables:
        variables.append({
            "address": v.address,
            "name": v.name,
            "data_type": v.datatype,  # 前端用 data_type 字段名
            "comment": v.comment,
        })

    networks = []
    for n in prog.networks:
        rungs = []
        for r in n.rungs:
            rungs.append({
                "elements": [_element_to_dict(e) for e in r.elements],
            })
        networks.append({
            "number": n.number,
            "title": n.title,
            "comment": n.comment,
            "rungs": rungs,
        })

    return {
        "title": prog.networks[0].title if prog.networks else "",
        "description": "",
        "variables": variables,
        "networks": networks,
    }
