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


def _ladder_to_scl(ladder_code: str, variables: list) -> Optional[str]:
    """尝试从简单的梯形图 ASCII 代码推导 SCL 逻辑

    仅处理最简单的情况：
    - 串联触点 → AND
    - 常闭触点 |/| → NOT
    - 线圈 ( ) → 赋值
    """
    import re

    lines = ladder_code.strip().split("\n")
    if not lines:
        return None

    # 提取第一行的触点和线圈
    first_line = lines[0]

    # 查找所有触点 --| |-- (常开) 和 --|/|-- (常闭)
    contacts_no = re.findall(r'(\w+)\s*\n?\s*[-─]+\|\s*\|', first_line)  # 常开
    contacts_nc = re.findall(r'(\w+)\s*\n?\s*[-─]+\|/\|', first_line)  # 常闭

    # 查找线圈 --( )--
    coils = re.findall(r'(\w+)\s*\n?\s*[-─]*\(\s*\)', first_line)

    # 也从所有行中提取
    full_text = " ".join(lines)
    if not contacts_no:
        contacts_no = re.findall(r'(\w+)\s*\n?\s*[-─]+\|\s*\|', full_text)
    if not contacts_nc:
        contacts_nc = re.findall(r'(\w+)\s*\n?\s*[-─]+\|/\|', full_text)
    if not coils:
        coils = re.findall(r'(\w+)\s*\n?\s*[-─]*\(\s*\)', full_text)

    if not coils:
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
    scl_lines = []
    for coil in coils:
        if coil and not coil.startswith("-"):
            scl_lines.append(f"    {coil} := {expr};")

    # 检查是否有自锁（第二行有同名变量的触点）
    if len(lines) > 2:
        for coil in coils:
            if coil in " ".join(lines[1:]):
                scl_lines.append(f"    // 自锁保持")
                scl_lines.append(f"    {coil} := {coil} OR ({expr});")
                break

    return "\n".join(scl_lines) if scl_lines else None
