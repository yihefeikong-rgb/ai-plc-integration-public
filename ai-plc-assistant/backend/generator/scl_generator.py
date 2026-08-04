"""SCL 源代码生成器 — 从 LadderProgram 生成 TIA Portal SCL 文件"""

from datetime import datetime
from typing import Optional

from generator import LadderProgram, Variable


def generate_scl(
    program: LadderProgram,
    block_type: str = "FB",
    block_name: Optional[str] = None,
) -> str:
    """将 LadderProgram 转换为 TIA Portal SCL 源代码

    Args:
        program: 梯形图程序数据
        block_type: 块类型 (FB/FC/OB)
        block_name: 块名称（默认使用 program.title）

    Returns:
        SCL 源代码字符串
    """
    name = block_name or _sanitize_name(program.title)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []

    # 块声明
    block_keyword = {
        "FB": "FUNCTION_BLOCK",
        "FC": "FUNCTION",
        "OB": "ORGANIZATION_BLOCK",
        "DB": "DATA_BLOCK",
    }.get(block_type, "FUNCTION_BLOCK")

    lines.append(f'{block_keyword} "{name}"')
    lines.append(f"TITLE = '{program.title}'")
    lines.append(f"// {program.description}")
    lines.append(f"// 生成时间: {timestamp}")
    lines.append(f"// 由 AI PLC Assistant 自动生成")
    lines.append("VERSION : 0.1")
    lines.append("")

    # 变量分类
    inputs = [v for v in program.variables if v.address.startswith(("I", "%I"))]
    outputs = [v for v in program.variables if v.address.startswith(("Q", "%Q"))]
    internals = [v for v in program.variables if v.address.startswith(("M", "%M"))]
    # 未分类的变量放到 input
    classified = set(v.name for v in inputs + outputs + internals)
    for v in program.variables:
        if v.name not in classified:
            inputs.append(v)

    # VAR_INPUT
    if inputs:
        lines.append("VAR_INPUT")
        for v in inputs:
            comment = f"   // {v.comment}" if v.comment else ""
            lines.append(f"    {v.name} : {v.data_type};{comment}")
        lines.append("END_VAR")
        lines.append("")

    # VAR_OUTPUT
    if outputs:
        lines.append("VAR_OUTPUT")
        for v in outputs:
            comment = f"   // {v.comment}" if v.comment else ""
            lines.append(f"    {v.name} : {v.data_type};{comment}")
        lines.append("END_VAR")
        lines.append("")

    # VAR (internal)
    if internals:
        lines.append("VAR")
        for v in internals:
            comment = f"   // {v.comment}" if v.comment else ""
            lines.append(f"    {v.name} : {v.data_type};{comment}")
        lines.append("END_VAR")
        lines.append("")

    # VAR_TEMP
    lines.append("VAR_TEMP")
    lines.append("    // 临时变量")
    lines.append("END_VAR")
    lines.append("")

    # BEGIN
    lines.append("BEGIN")
    lines.append("")

    # Networks → SCL 逻辑
    for n in program.networks:
        lines.append(f"// =============================================")
        lines.append(f"// Network {n.number}: {n.title}")
        lines.append(f"// =============================================")
        if n.comment:
            lines.append(f"// {n.comment}")

        # 将梯形图 ASCII 转换为 SCL 逻辑注释
        if n.code:
            lines.append("//")
            lines.append("// 梯形图:")
            for code_line in n.code.split("\n"):
                lines.append(f"//   {code_line}")
            lines.append("//")

            # 尝试从梯形图提取简单的赋值逻辑
            scl_logic = _ladder_to_scl(n.code, program.variables)
            if scl_logic:
                lines.append(scl_logic)
            else:
                lines.append(f"// TODO: 请根据上方梯形图手动编写 SCL 逻辑")
                lines.append(f"// Network {n.number} 的 SCL 代码")
                lines.append(";")

        lines.append("")

    # 块结束
    end_keyword = {
        "FB": "END_FUNCTION_BLOCK",
        "FC": "END_FUNCTION",
        "OB": "END_ORGANIZATION_BLOCK",
        "DB": "END_DATA_BLOCK",
    }.get(block_type, "END_FUNCTION_BLOCK")
    lines.append(end_keyword)

    return "\n".join(lines)


def _sanitize_name(title: str) -> str:
    """将标题转换为合法的块名称"""
    # 取前20个字符，替换非法字符
    name = title[:30].strip()
    safe = []
    for ch in name:
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        elif ch in (" ", "-", "/"):
            safe.append("_")
    result = "".join(safe).strip("_")
    return result or "GeneratedBlock"


def _parse_rungs(ladder_code: str) -> list:
    """将梯形图 ASCII 文本解析为 rung 列表。

    每个 rung 为 (常开触点, 常闭触点, 线圈, 分支触点) 四元组。
    兼容双行式 ASCII-LAD-V2（名称行在上、--| |--( ) 符号行在下，
    由 _rungs_to_ascii 从结构化 rungs 重建）与旧式单行梯形图。

    若双行式未解析出任何线圈，则回退到旧式单行正则解析（名称紧贴符号），
    保留原有解析行为与自锁启发式。
    """
    import re

    rows = [ln.strip() for ln in ladder_code.split("\n") if ln.strip()]
    if not rows:
        return []

    symbol_pattern = re.compile(r"\| \||\|/\||\( \)")
    rungs: list = []
    current = None
    pending_names: list = []

    for line in rows:
        symbols = symbol_pattern.findall(line)
        if symbols:
            names = pending_names if pending_names else [""] * len(symbols)
            if line.startswith("+"):
                # 分支符号行：并联路径触点归属当前 rung
                if current is None:
                    current = {"no": [], "nc": [], "coils": [], "branch": []}
                    rungs.append(current)
                for i, _ in enumerate(symbols):
                    if i < len(names) and names[i]:
                        current["branch"].append(names[i])
            else:
                # 主符号行：新 rung，名称来自其上方紧邻的名称行
                current = {"no": [], "nc": [], "coils": [], "branch": []}
                rungs.append(current)
                for i, sym in enumerate(symbols):
                    name = names[i] if i < len(names) else ""
                    if sym == "( )":
                        current["coils"].append(name)
                    elif sym == "|/|":
                        current["nc"].append(name)
                    else:  # "| |"
                        current["no"].append(name)
            pending_names = []
        elif line.startswith(("--", "+")):
            # 定时器/比较器等无触点线圈的符号行：不产生 SCL，跳过
            pending_names = []
        elif line.startswith("| "):
            # 分支名称行：| qMotor
            pending_names = [t for t in line[2:].split() if re.fullmatch(r"[\w.]+", t)]
        elif set(line) <= {"|", " "}:
            # 分支连接竖线：忽略
            pass
        else:
            # 主名称行：白空格分隔的符号名
            pending_names = [t for t in line.split() if re.fullmatch(r"[\w.]+", t)]

    rungs = [(r["no"], r["nc"], r["coils"], r["branch"]) for r in rungs]

    # 兜底：旧式单行格式（名称紧贴符号），保留原正则解析与自锁启发式
    if not any(c for _, _, coils, _ in rungs for c in coils if c):
        full_text = " ".join(rows)
        contacts_no = re.findall(r'(\w+)\s*[-─]+\|\s*\|', full_text)
        contacts_nc = re.findall(r'(\w+)\s*[-─]+\|/\|', full_text)
        coils = re.findall(r'(\w+)\s*[-─]*\(\s*\)', full_text)
        if coils:
            branch_contacts = []
            if len(rows) > 2:
                below = " ".join(rows[1:])
                branch_contacts = [c for c in coils if c in below]
            rungs = [(contacts_no, contacts_nc, coils, branch_contacts)]

    return rungs


def _ladder_to_scl(ladder_code: str, variables: list) -> Optional[str]:
    """尝试从简单的梯形图 ASCII 代码推导 SCL 逻辑

    仅处理最简单的情况：
    - 串联触点 → AND
    - 常闭触点 |/| → NOT
    - 线圈 ( ) → 赋值

    支持双行式 ASCII-LAD-V2（名称行在上、--| |--( ) 符号行在下，
    由 _rungs_to_ascii 从结构化 rungs 重建）及旧式单行梯形图。
    """
    scl_lines = []

    for contacts_no, contacts_nc, coils, branch_contacts in _parse_rungs(ladder_code):
        # 并联分支仅支持线圈自锁反馈；其余并联逻辑本简单转换器无法
        # 可靠表示，fail-closed 交由人工编写。
        if not coils:
            return None
        if any(c for c in branch_contacts if c not in coils):
            return None

        # 构建 SCL 表达式
        conditions = []
        for c in contacts_no:
            if c and not c.startswith("-"):
                conditions.append(c)
        for c in contacts_nc:
            if c and not c.startswith("-"):
                conditions.append(f"NOT {c}")

        if not conditions:
            return None

        expr = " AND ".join(conditions)
        for coil in coils:
            if coil and not coil.startswith("-"):
                scl_lines.append(f"    {coil} := {expr};")

        # 检查是否有自锁（线圈名在并联分支中作为反馈触点出现）
        for coil in coils:
            if coil in branch_contacts:
                scl_lines.append(f"    // 自锁保持")
                scl_lines.append(f"    {coil} := {coil} OR ({expr});")
                break

    return "\n".join(scl_lines) if scl_lines else None
