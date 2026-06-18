"""
ascii_parser.py — ASCII-LAD-V2 解析器

输入: ASCII-LAD-V2 格式文本
输出: LadderProgram 数据模型

数据流:
    AI 生成的 ASCII 文本
        ↓
    AsciiLadParser.parse(text)
        ↓
    LadderProgram (ladder_model.py)
        ↓
    前端渲染 / SCL 导出 / XML 导出
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from generator.ladder_model import (
    LadderProgram, Network, Rung, Variable,
    Contact, Coil, Timer, Counter, Move, Comparator, BlockCall, Branch,
)


# ═══════════════════════════════════════════════════════════
# 元素识别模式（顺序重要：具体模式在前，通用模式在后）
# ═══════════════════════════════════════════════════════════

_ELEMENT_PATTERNS: list[tuple[re.Pattern, callable]] = [
    # 常闭触点: [/ name ]
    (re.compile(r'\[/\s+([\w.]+)\s+\]'),
     lambda m: Contact(m.group(1), normally_closed=True)),

    # 定时器: [TON name PT=time]
    (re.compile(r'\[(TON|TOF|TP)\s+([\w.]+)\s+PT=([\w.]+)\]'),
     lambda m: Timer(m.group(1), m.group(2), m.group(3))),

    # 计数器: [CTU name PV=num]
    (re.compile(r'\[(CTU|CTD)\s+([\w.]+)\s+PV=(\d+)\]'),
     lambda m: Counter(m.group(1), m.group(2), int(m.group(3)))),

    # MOVE V2.1: [MOVE IN=src OUT=dst]
    (re.compile(r'\[MOVE\s+IN=(\S+)\s+OUT=(\S+)\s*\]'),
     lambda m: Move(m.group(1), m.group(2))),

    # MOVE V2.0 兼容: [MOVE src -> dst]
    (re.compile(r'\[MOVE\s+(\S+)\s+->\s+(\S+)\s*\]'),
     lambda m: Move(m.group(1), m.group(2))),

    # 比较器: [CMP op a b]
    (re.compile(r'\[CMP\s+(EQ|NE|GT|GE|LT|LE)\s+(\S+)\s+(\S+)\s*\]'),
     lambda m: Comparator(m.group(1), m.group(2), m.group(3))),

    # FB/FC 调用: [FB name] / [FC name]
    (re.compile(r'\[(FB|FC)\s+([\w.]+)\s*\]'),
     lambda m: BlockCall(m.group(1), m.group(2))),

    # 常开触点: [ name ] （通用方括号，放在所有方括号模式之后）
    (re.compile(r'\[\s+([\w.]+)\s+\]'),
     lambda m: Contact(m.group(1), normally_closed=False)),

    # 置位线圈: (S name)
    (re.compile(r'\(S\s+([\w.]+)\)'),
     lambda m: Coil(m.group(1), kind="set")),

    # 复位线圈: (R name)
    (re.compile(r'\(R\s+([\w.]+)\)'),
     lambda m: Coil(m.group(1), kind="reset")),

    # 普通线圈: ( name ) （通用圆括号，放最后）
    (re.compile(r'\(\s+([\w.]+)\s+\)'),
     lambda m: Coil(m.group(1), kind="normal")),
]


# ═══════════════════════════════════════════════════════════
# 元素提取
# ═══════════════════════════════════════════════════════════

def extract_elements(text: str) -> list:
    """从一行文本中提取所有梯形图元素，按出现顺序返回。"""
    matches: list[tuple[int, int, object]] = []

    for pattern, factory in _ELEMENT_PATTERNS:
        for m in re.finditer(pattern, text):
            matches.append((m.start(), m.end(), factory(m)))

    matches.sort(key=lambda x: x[0])

    # 去重：跳过被前面匹配覆盖的区间
    result = []
    last_end = -1
    for start, end, elem in matches:
        if start >= last_end:
            result.append(elem)
            last_end = end

    return result


# ═══════════════════════════════════════════════════════════
# Rung 解析（含 Branch）
# ═══════════════════════════════════════════════════════════

def _find_junction(line: str) -> int:
    """查找 Branch 连接点 + 的列位置。返回 -1 表示无分支。

    跳过方括号 / 圆括号 内部的 + 字符。
    """
    depth_sq = 0   # [] 深度
    depth_rd = 0   # () 深度
    for i, ch in enumerate(line):
        if ch == '[':
            depth_sq += 1
        elif ch == ']':
            depth_sq = max(0, depth_sq - 1)
        elif ch == '(':
            depth_rd += 1
        elif ch == ')':
            depth_rd = max(0, depth_rd - 1)
        elif ch == '+' and depth_sq == 0 and depth_rd == 0:
            return i
    return -1


def _is_branch_connector(line: str, junction_col: int) -> bool:
    """判断是否是分支竖线连接行（只有 | 和空格）。"""
    stripped = line.rstrip()
    if not stripped:
        return False
    # 在 junction_col 位置应该有 |
    if junction_col < len(stripped) and stripped[junction_col] == '|':
        # 整行只有 |、空格
        return all(ch in '| ' for ch in stripped)
    return False


def _is_branch_path(line: str, junction_col: int) -> bool:
    """判断是否是分支路径行（以 |---- 开头，在 junction_col 处有 +）。"""
    stripped = line.rstrip()
    if not stripped.startswith('|'):
        return False
    if '----' not in stripped:
        return False
    # 检查在 junction_col 位置附近有 +
    if junction_col < len(stripped) and stripped[junction_col] == '+':
        return True
    # 行末尾有 +
    if stripped.endswith('+'):
        return True
    return False


def parse_rung_block(lines: list[str]) -> Rung:
    """解析一个 Rung 块（主行 + 可能的分支行）为 Rung 对象。"""
    if not lines:
        return Rung()

    main_line = lines[0]
    junction_col = _find_junction(main_line)

    # 无分支：简单串联
    if junction_col == -1:
        elements = extract_elements(main_line)
        return Rung(elements=elements)

    # 有分支：分割主行
    before_junction = main_line[:junction_col]
    after_junction = main_line[junction_col + 1:]

    main_path = extract_elements(before_junction)
    output_elements = extract_elements(after_junction)

    # 收集分支路径
    branch_paths: list[list] = []
    for line in lines[1:]:
        if _is_branch_connector(line, junction_col):
            continue
        if _is_branch_path(line, junction_col):
            elements = extract_elements(line)
            if elements:
                branch_paths.append(elements)

    branch = Branch(paths=[main_path] + branch_paths)
    return Rung(elements=[branch] + output_elements)


# ═══════════════════════════════════════════════════════════
# 主解析器
# ═══════════════════════════════════════════════════════════

@dataclass
class ParseWarning:
    """解析警告"""
    line_number: int
    message: str


class AsciiLadParser:
    """ASCII-LAD-V2 解析器

    用法：
        parser = AsciiLadParser()
        program = parser.parse(text)
        if parser.warnings:
            for w in parser.warnings:
                print(f"Line {w.line_number}: {w.message}")
    """

    def __init__(self):
        self.warnings: list[ParseWarning] = []

    def _warn(self, line_no: int, msg: str):
        self.warnings.append(ParseWarning(line_no, msg))

    def parse(self, text: str) -> LadderProgram:
        """解析 ASCII-LAD-V2 文本为 LadderProgram。"""
        self.warnings = []
        lines = text.splitlines()

        program = LadderProgram()
        idx = 0
        total = len(lines)

        # ── Step 1: 查找版本头 ──
        while idx < total:
            stripped = lines[idx].strip()
            if stripped:
                if stripped.startswith('ASCII-LAD-V'):
                    program.version = stripped
                    idx += 1
                    break
                else:
                    self._warn(idx + 1, f"期望版本头 ASCII-LAD-V2，实际: {stripped}")
                    break
            idx += 1

        # ── Step 2: 主循环 ──
        while idx < total:
            stripped = lines[idx].strip()

            # 空行跳过
            if not stripped:
                idx += 1
                continue

            # 变量表
            if stripped == 'Variables:':
                idx += 1
                idx = self._parse_variables(lines, idx, total, program)
                continue

            # Network
            m = re.match(r'^Network\s+(\d+)$', stripped)
            if m:
                network_num = int(m.group(1))
                idx += 1
                network, idx = self._parse_network(lines, idx, total, network_num)
                program.networks.append(network)
                continue

            # 无法识别的行
            self._warn(idx + 1, f"无法识别: {stripped}")
            idx += 1

        return program

    def _parse_variables(self, lines: list[str], idx: int, total: int, program: LadderProgram) -> int:
        """解析变量表区域，返回下一行索引。"""
        while idx < total:
            stripped = lines[idx].strip()

            # 空行结束变量区
            if not stripped:
                idx += 1
                return idx

            # 遇到 Network 则不消费此行，退出
            if stripped.startswith('Network '):
                return idx

            # 解析变量行: address  name  type  [comment]
            parts = stripped.split(None, 3)
            if len(parts) >= 3:
                var = Variable(
                    address=parts[0],
                    name=parts[1],
                    datatype=parts[2],
                    comment=parts[3] if len(parts) > 3 else "",
                )
                program.variables.append(var)
            else:
                self._warn(idx + 1, f"变量格式错误（需要至少 3 个字段）: {stripped}")

            idx += 1

        return idx

    def _parse_network(self, lines: list[str], idx: int, total: int, number: int) -> tuple[Network, int]:
        """解析一个 Network，返回 (Network 对象, 下一行索引)。"""
        network = Network(number=number)

        # ── Title (可选) ──
        if idx < total:
            stripped = lines[idx].strip()
            if stripped.startswith('Title:'):
                network.title = stripped[len('Title:'):].strip()
                idx += 1

        # ── 跳过空行 ──
        while idx < total and not lines[idx].strip():
            idx += 1

        # ── Comment (可选) ──
        if idx < total:
            stripped = lines[idx].strip()
            if stripped == 'Comment:':
                idx += 1
                comment_lines = []
                while idx < total:
                    line = lines[idx]
                    stripped = line.strip()
                    # Comment 结束条件：空行、|---- 开头、Network 开头
                    if not stripped or stripped.startswith('|') or stripped.startswith('Network '):
                        break
                    comment_lines.append(stripped)
                    idx += 1
                network.comment = '\n'.join(comment_lines)

        # ── 跳过空行 ──
        while idx < total and not lines[idx].strip():
            idx += 1

        # ── Rung 行 ──
        while idx < total:
            stripped = lines[idx].strip()

            # 空行可能分隔多个 rung
            if not stripped:
                idx += 1
                # 检查下一个非空行是否还是 rung
                peek = idx
                while peek < total and not lines[peek].strip():
                    peek += 1
                if peek < total and lines[peek].strip().startswith('Network '):
                    return network, idx
                # 如果后面还有 rung 行就继续
                continue

            # 遇到下一个 Network，退出
            if stripped.startswith('Network '):
                return network, idx

            # 收集一个 rung 块（主行 + 分支行）
            if stripped.startswith('|'):
                rung_lines = [lines[idx]]
                idx += 1
                # 收集后续行（分支连接行和分支路径行）
                while idx < total:
                    line = lines[idx]
                    s = line.strip()
                    if not s:
                        break
                    if s.startswith('Network '):
                        break
                    # 分支连接行或分支路径行
                    if s.startswith('|'):
                        rung_lines.append(line)
                        idx += 1
                    else:
                        break

                rung = parse_rung_block(rung_lines)
                network.rungs.append(rung)
                continue

            # 无法识别的行
            self._warn(idx + 1, f"Network {number} 中无法识别: {stripped}")
            idx += 1

        return network, idx


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def parse_ascii_lad(text: str) -> LadderProgram:
    """解析 ASCII-LAD-V2 文本，返回 LadderProgram。

    Args:
        text: ASCII-LAD-V2 格式文本

    Returns:
        LadderProgram 实例

    Raises:
        不抛异常。解析错误记录在 parser.warnings 中。
    """
    parser = AsciiLadParser()
    return parser.parse(text)


def parse_ascii_lad_with_warnings(text: str) -> tuple[LadderProgram, list[ParseWarning]]:
    """解析并返回警告列表。"""
    parser = AsciiLadParser()
    program = parser.parse(text)
    return program, parser.warnings
