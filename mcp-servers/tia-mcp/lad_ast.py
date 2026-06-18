"""
LAD AST — 梯形图统一抽象语法树

作为所有梯形图操作的统一中间表示：
  JSON → AST → SVG / TIA XML / SCL / PDF / PNG

所有类型为 Python dataclass，支持 to_dict()/from_dict() 序列化。
遵循 IEC 61131-3 梯形图概念。
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ═══════════════════════════════════════════════════════════
# 枚举类型
# ═══════════════════════════════════════════════════════════

class ContactPolarity(str, Enum):
    """触点极性"""
    NO = "normally_open"      # 常开 |-| |
    NC = "normally_closed"    # 常闭 |-/|


class CoilKind(str, Enum):
    """线圈类型"""
    OUT = "coil"              # 普通线圈 ( )
    SET = "coil_set"          # 置位线圈 (S)
    RESET = "coil_reset"      # 复位线圈 (R)


class TimerType(str, Enum):
    """IEC 定时器类型"""
    TON = "TON"      # 接通延时
    TOF = "TOF"      # 断开延时
    TP = "TP"        # 脉冲


class CounterType(str, Enum):
    """计数器类型"""
    CTU = "CTU"      # 加计数
    CTD = "CTD"      # 减计数


class ComparatorOp(str, Enum):
    """比较运算"""
    EQ = "EQ"   # ==
    NE = "NE"   # <>
    GT = "GT"   # >
    GE = "GE"   # >=
    LT = "LT"   # <
    LE = "LE"   # <=


class MathOp(str, Enum):
    """算术运算"""
    ADD = "ADD"
    SUB = "SUB"
    MUL = "MUL"
    DIV = "DIV"
    MOD = "MOD"
    NEG = "NEG"  # 取反


class VarScope(str, Enum):
    """变量作用域"""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    INOUT = "IN_OUT"
    STATIC = "STATIC"
    TEMP = "TEMP"
    GLOBAL = "GLOBAL"  # DB 全局变量


# ═══════════════════════════════════════════════════════════
# 操作数引用
# ═══════════════════════════════════════════════════════════

@dataclass
class OperandRef:
    """
    操作数引用 — 符号名 + 地址 + 类型。
    与 LadderSpec JSON 的 interface 条目对应。
    """
    name: str                            # 符号名 (如 "bStart")
    address: str = ""                    # 物理地址 (如 "%I0.1")
    data_type: str = "Bool"              # 数据类型
    scope: VarScope = VarScope.STATIC    # 作用域
    comment: str = ""                    # 注释

    def to_dict(self) -> dict:
        d = {"name": self.name, "data_type": self.data_type}
        if self.address:
            d["address"] = self.address
        if self.comment:
            d["comment"] = self.comment
        return d

    @classmethod
    def from_dict(cls, d: dict) -> OperandRef:
        return cls(
            name=d.get("name", ""),
            address=d.get("address", ""),
            data_type=d.get("data_type", "Bool"),
            scope=VarScope(d.get("scope", "STATIC")) if d.get("scope") else VarScope.STATIC,
            comment=d.get("comment", ""),
        )


# ═══════════════════════════════════════════════════════════
# 接口变量
# ═══════════════════════════════════════════════════════════

@dataclass
class InterfaceVariable:
    """接口变量 — 与 LadderSpec JSON 的 interface 条目一致"""
    name: str
    data_type: str = "Bool"
    comment: str = ""
    address: str = ""         # 物理地址 (可选)

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.data_type, "comment": self.comment}
        if self.address:
            d["address"] = self.address
        return d

    @classmethod
    def from_dict(cls, d: dict) -> InterfaceVariable:
        return cls(
            name=d["name"],
            data_type=d.get("type", d.get("data_type", "Bool")),
            comment=d.get("comment", ""),
            address=d.get("address", ""),
        )


# ═══════════════════════════════════════════════════════════
# 梯级元素 (AST 节点)
# ═══════════════════════════════════════════════════════════

@dataclass
class LadderElement:
    """所有梯级元素的基类"""
    type: str = "element"
    comment: str = ""

    def to_dict(self) -> dict:
        return {"type": self.type}

    @classmethod
    def from_dict(cls, d: dict) -> LadderElement:
        """工厂方法：根据 type 字段创建对应子类实例"""
        etype = d.get("type", "")
        if etype in ("normally_open", "normally_closed"):
            return Contact.from_dict(d)
        elif etype in ("coil", "coil_set", "coil_reset"):
            return Coil.from_dict(d)
        elif etype == "branch":
            return Branch.from_dict(d)
        elif etype == "timer":
            return Timer.from_dict(d)
        elif etype == "counter":
            return Counter.from_dict(d)
        elif etype in ("EQ", "NE", "GT", "GE", "LT", "LE"):
            return Comparator.from_dict(d)
        elif etype in ("ADD", "SUB", "MUL", "DIV", "MOD", "NEG"):
            return MathElement.from_dict(d)
        elif etype == "move":
            return MoveElement.from_dict(d)
        elif etype == "box":
            return BoxCall.from_dict(d)  # 功能块调用
        elif etype == "empty":
            return EmptyElement.from_dict(d)
        else:
            return cls(type=etype)


# ── 触点 ──────────────────────────────────────────────────

@dataclass
class Contact(LadderElement):
    """触点：常开/常闭"""
    type: str = "normally_open"
    polarity: ContactPolarity = ContactPolarity.NO
    operand: OperandRef = field(default_factory=OperandRef)

    def __post_init__(self):
        # 确保 type 与 polarity 一致
        if self.type == "normally_closed":
            self.polarity = ContactPolarity.NC

    def to_dict(self) -> dict:
        return {
            "type": self.polarity.value,
            "operand": self.operand.name,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Contact:
        polarity = ContactPolarity(d.get("type", "normally_open"))
        return cls(
            type=polarity.value,
            polarity=polarity,
            operand=OperandRef(name=d.get("operand", "")),
            comment=d.get("comment", ""),
        )


# ── 线圈 ──────────────────────────────────────────────────

@dataclass
class Coil(LadderElement):
    """线圈：输出/置位/复位"""
    type: str = "coil"
    kind: CoilKind = CoilKind.OUT
    operand: OperandRef = field(default_factory=OperandRef)

    def __post_init__(self):
        kind_map = {
            "coil": CoilKind.OUT,
            "coil_set": CoilKind.SET,
            "coil_reset": CoilKind.RESET,
        }
        self.kind = kind_map.get(self.type, CoilKind.OUT)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "operand": self.operand.name,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Coil:
        etype = d.get("type", "coil")
        return cls(
            type=etype,
            kind={"coil": CoilKind.OUT, "coil_set": CoilKind.SET, "coil_reset": CoilKind.RESET}.get(etype, CoilKind.OUT),
            operand=OperandRef(name=d.get("operand", "")),
            comment=d.get("comment", ""),
        )


# ── 并联分支 ──────────────────────────────────────────────

@dataclass
class Branch(LadderElement):
    """
    并联分支。
    paths 中的每条 path 是一串元素。
    起点分支，终点汇合。
    """
    type: str = "branch"
    paths: list[list[LadderElement]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": "branch",
            "paths": [
                [el.to_dict() for el in path]
                for path in self.paths
            ],
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Branch:
        paths = []
        for raw_path in d.get("paths", []):
            path = [LadderElement.from_dict(el) for el in raw_path]
            paths.append(path)
        return cls(paths=paths, comment=d.get("comment", ""))


# ── 空占位 ────────────────────────────────────────────────

@dataclass
class EmptyElement(LadderElement):
    """空元素 — 用于网格占位/对齐"""
    type: str = "empty"

    def to_dict(self) -> dict:
        return {"type": "empty"}

    @classmethod
    def from_dict(cls, d: dict) -> EmptyElement:
        return cls()


# ── IEC 定时器 ────────────────────────────────────────────

@dataclass
class Timer(LadderElement):
    """IEC 定时器 — TON/TOF/TP"""
    type: str = "timer"
    timer_type: TimerType = TimerType.TON
    instance: str = ""         # 实例名 (如 "tonMyTimer")
    preset: str = "T#5S"       # 设定值
    q_operand: Optional[OperandRef] = None   # .Q 输出 (可选)
    et_operand: Optional[OperandRef] = None  # .ET 当前值 (可选)
    in_operand: Optional[OperandRef] = None  # 外部 IN 输入 (可选，不设则用触点链)

    def to_dict(self) -> dict:
        d = {"type": "timer", "timer_type": self.timer_type.value,
             "instance": self.instance, "preset": self.preset, "comment": self.comment}
        if self.q_operand:
            d["q_operand"] = self.q_operand.name
        if self.et_operand:
            d["et_operand"] = self.et_operand.name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Timer:
        return cls(
            timer_type=TimerType(d.get("timer_type", "TON")),
            instance=d.get("instance", ""),
            preset=d.get("preset", "T#5S"),
            q_operand=OperandRef(name=d["q_operand"]) if d.get("q_operand") else None,
            et_operand=OperandRef(name=d["et_operand"]) if d.get("et_operand") else None,
            comment=d.get("comment", ""),
        )


# ── IEC 计数器 ────────────────────────────────────────────

@dataclass
class Counter(LadderElement):
    """IEC 计数器 — CTU/CTD"""
    type: str = "counter"
    counter_type: CounterType = CounterType.CTU
    instance: str = ""
    preset: str = "5"          # PV 设定值
    q_operand: Optional[OperandRef] = None   # .Q 输出
    cv_operand: Optional[OperandRef] = None  # .CV 当前值

    def to_dict(self) -> dict:
        d = {"type": "counter", "counter_type": self.counter_type.value,
             "instance": self.instance, "preset": self.preset, "comment": self.comment}
        if self.q_operand:
            d["q_operand"] = self.q_operand.name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Counter:
        return cls(
            counter_type=CounterType(d.get("counter_type", "CTU")),
            instance=d.get("instance", ""),
            preset=d.get("preset", "5"),
            q_operand=OperandRef(name=d["q_operand"]) if d.get("q_operand") else None,
            comment=d.get("comment", ""),
        )


# ── 比较器 ────────────────────────────────────────────────

@dataclass
class Comparator(LadderElement):
    """比较指令 — 相当于 CMP"""
    type: str = "EQ"
    op: ComparatorOp = ComparatorOp.EQ
    operand_a: OperandRef = field(default_factory=OperandRef)
    operand_b: OperandRef = field(default_factory=OperandRef)

    def __post_init__(self):
        self.op = ComparatorOp(self.type)

    def to_dict(self) -> dict:
        return {
            "type": self.op.value,
            "operand_a": self.operand_a.name,
            "operand_b": self.operand_b.name,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Comparator:
        op = ComparatorOp(d.get("type", "EQ"))
        return cls(
            type=op.value, op=op,
            operand_a=OperandRef(name=d.get("operand_a", "")),
            operand_b=OperandRef(name=d.get("operand_b", "")),
            comment=d.get("comment", ""),
        )


# ── 算术运算 ──────────────────────────────────────────────

@dataclass
class MathElement(LadderElement):
    """算术运算 — ADD/SUB/MUL/DIV"""
    type: str = "ADD"
    op: MathOp = MathOp.ADD
    dest: OperandRef = field(default_factory=OperandRef)
    src_a: OperandRef = field(default_factory=OperandRef)
    src_b: Optional[OperandRef] = None

    def __post_init__(self):
        self.op = MathOp(self.type)

    def to_dict(self) -> dict:
        d = {"type": self.op.value, "dest": self.dest.name, "src_a": self.src_a.name, "comment": self.comment}
        if self.src_b:
            d["src_b"] = self.src_b.name
        return d

    @classmethod
    def from_dict(cls, d: dict) -> MathElement:
        op = MathOp(d.get("type", "ADD"))
        return cls(
            type=op.value, op=op,
            dest=OperandRef(name=d.get("dest", "")),
            src_a=OperandRef(name=d.get("src_a", "")),
            src_b=OperandRef(name=d["src_b"]) if d.get("src_b") else None,
            comment=d.get("comment", ""),
        )


# ── 传送指令 ──────────────────────────────────────────────

@dataclass
class MoveElement(LadderElement):
    """MOVE 传送"""
    type: str = "move"
    src: OperandRef = field(default_factory=OperandRef)
    dest: OperandRef = field(default_factory=OperandRef)

    def to_dict(self) -> dict:
        return {"type": "move", "src": self.src.name, "dest": self.dest.name, "comment": self.comment}

    @classmethod
    def from_dict(cls, d: dict) -> MoveElement:
        return cls(
            src=OperandRef(name=d.get("src", "")),
            dest=OperandRef(name=d.get("dest", "")),
            comment=d.get("comment", ""),
        )


# ── 功能块调用 (BOX) ─────────────────────────────────────

@dataclass
class BoxCall(LadderElement):
    """
    功能块调用 — 如定时器/计数器或用户自定义 FB。
    表示为 TIA 风格的矩形框。
    """
    type: str = "box"
    box_type: str = ""          # 功能块类型名 (如 "TON", "CTU", "MyFB")
    instance: str = ""           # 实例名 (如 "tonDelay", "myFB_1")
    inputs: dict[str, str] = field(default_factory=dict)   # 输入参数名→操作数
    outputs: dict[str, str] = field(default_factory=dict)  # 输出参数名→操作数

    def to_dict(self) -> dict:
        return {
            "type": "box",
            "box_type": self.box_type,
            "instance": self.instance,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, d: dict) -> BoxCall:
        return cls(
            box_type=d.get("box_type", ""),
            instance=d.get("instance", ""),
            inputs=d.get("inputs", {}),
            outputs=d.get("outputs", {}),
            comment=d.get("comment", ""),
        )


# ═══════════════════════════════════════════════════════════
# 梯级 (Rung)
# ═══════════════════════════════════════════════════════════

@dataclass
class LadderRung:
    """
    梯级 — 从左电源轨到右电源轨的完整电路。
    main_path: 主路径（串联元素序列）
    分支通过 Branch 元素在 main_path 中引入。
    """
    elements: list[LadderElement] = field(default_factory=list)

    def to_dict(self) -> list[dict]:
        return [el.to_dict() for el in self.elements]

    @classmethod
    def from_dict(cls, data: list[dict]) -> LadderRung:
        return cls(elements=[LadderElement.from_dict(el) for el in data])


# ═══════════════════════════════════════════════════════════
# Network — 网络
# ═══════════════════════════════════════════════════════════

@dataclass
class LadderNetwork:
    """
    网络 — 一个梯形图网络（对应 TIA Portal 中的一个 Network）。
    包含一个梯级（主逻辑）和元数据。
    """
    index: int = 0
    title: str = ""
    comment: str = ""
    rung: LadderRung = field(default_factory=LadderRung)

    def to_dict(self) -> dict:
        d = {"title": self.title, "comment": self.comment}
        elements = self.rung.to_dict()
        if elements:
            d["elements"] = elements
        return d

    @classmethod
    def from_dict(cls, d: dict, index: int = 0) -> LadderNetwork:
        elements = d.get("elements", [])
        return cls(
            index=index,
            title=d.get("title", ""),
            comment=d.get("comment", ""),
            rung=LadderRung.from_dict(elements),
        )


# ═══════════════════════════════════════════════════════════
# Block — 功能块 (顶层)
# ═══════════════════════════════════════════════════════════

@dataclass
class LadderBlock:
    """
    梯形图功能块 — 顶层对象。
    对应 TIA Portal 中的一个 FB/FC/DB。
    """
    name: str = ""
    number: int = 0
    networks: list[LadderNetwork] = field(default_factory=list)
    inputs: list[InterfaceVariable] = field(default_factory=list)
    outputs: list[InterfaceVariable] = field(default_factory=list)
    inouts: list[InterfaceVariable] = field(default_factory=list)
    statics: list[InterfaceVariable] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "blockName": self.name,
            "blockNumber": self.number,
            "networks": [n.to_dict() for n in self.networks],
        }
        interface = {}
        if self.inputs:
            interface["inputs"] = [v.to_dict() for v in self.inputs]
        if self.outputs:
            interface["outputs"] = [v.to_dict() for v in self.outputs]
        if self.inouts:
            interface["inouts"] = [v.to_dict() for v in self.inouts]
        if self.statics:
            interface["static"] = [v.to_dict() for v in self.statics]
        if interface:
            d["interface"] = interface
        return d

    @classmethod
    def from_dict(cls, d: dict) -> LadderBlock:
        """从 LadderSpec JSON dict 构建 AST"""
        iface = d.get("interface", {})
        networks_raw = d.get("networks", [])

        return cls(
            name=d.get("blockName", ""),
            number=d.get("blockNumber", 0),
            inputs=[InterfaceVariable.from_dict(v) for v in iface.get("inputs", [])],
            outputs=[InterfaceVariable.from_dict(v) for v in iface.get("outputs", [])],
            inouts=[InterfaceVariable.from_dict(v) for v in iface.get("inouts", [])],
            statics=[InterfaceVariable.from_dict(v) for v in iface.get("static", [])],
            networks=[
                LadderNetwork.from_dict(n, idx)
                for idx, n in enumerate(networks_raw, 1)
            ],
        )

    def to_json_str(self, indent: int = 2) -> str:
        """导出为 JSON 字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def element_from_ladder_spec(spec: dict) -> LadderElement:
    """从 LadderSpec JSON 元素创建 AST 元素（工厂）"""
    return LadderElement.from_dict(spec)


def ast_to_ladder_spec_elements(rung: LadderRung) -> list[dict]:
    """
    将 AST 梯级转换为 LadderSpec JSON elements 列表。
    用于向后兼容：旧的渲染器/导出器可以消费 AST 的输出。
    """
    elements = []
    for el in rung.elements:
        if isinstance(el, (Contact, Coil)):
            # 简单元素直接输出
            elements.append(el.to_dict())
        elif isinstance(el, Branch):
            # 分支→尝试摊平为多个 network
            # 当前 LadderSpec 不支持分支，摊平会丢失结构
            # 标记为注释
            for path in el.paths:
                for sub_el in path:
                    elements.append(sub_el.to_dict())
        elif isinstance(el, EmptyElement):
            continue  # 跳过占位
        else:
            elements.append(el.to_dict())
    return elements
