"""PLCopen XML 生成器 — 从 LadderProgram 生成可导入 TIA Portal 的 XML 文件"""

import uuid
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring, indent
from typing import Optional

from generator import LadderProgram


PLCOPEN_NS = "http://www.plcopen.org/xml/tc6_0201"


def generate_xml(
    program: LadderProgram,
    block_type: str = "FB",
    block_name: Optional[str] = None,
    author: str = "AI PLC Assistant",
) -> str:
    """将 LadderProgram 转换为 PLCopen XML

    Args:
        program: 梯形图程序数据
        block_type: 块类型 (FB/FC)
        block_name: 块名称
        author: 作者信息

    Returns:
        PLCopen XML 字符串
    """
    name = block_name or _sanitize(program.title)
    now = datetime.now().isoformat()

    # 根元素
    root = Element("project", xmlns=PLCOPEN_NS)
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")

    # fileHeader
    fh = SubElement(root, "fileHeader")
    fh.set("companyName", author)
    fh.set("productName", "AI PLC Assistant")
    fh.set("productVersion", "1.0")
    fh.set("creationDateTime", now)

    # contentHeader
    ch = SubElement(root, "contentHeader")
    ch.set("name", name)
    ch.set("modificationDateTime", now)
    coord = SubElement(ch, "coordinateInfo")
    for dim in ("fbd", "ld", "sfc"):
        info = SubElement(coord, dim)
        SubElement(info, "scaling", x="1", y="1")

    # types → pous
    types = SubElement(root, "types")
    data_types = SubElement(types, "dataTypes")
    pous = SubElement(types, "pous")

    pou_type = "functionBlock" if block_type == "FB" else "function"
    pou = SubElement(pous, "pou", name=name, pouType=pou_type)

    # documentation
    if program.description:
        doc = SubElement(pou, "documentation")
        xhtml = SubElement(doc, "xhtml", xmlns="http://www.w3.org/1999/xhtml")
        xhtml.text = program.description

    # interface (variables)
    interface = SubElement(pou, "interface")
    _build_interface(interface, program)

    # body (networks)
    body = SubElement(pou, "body")
    _build_body(body, program, block_type)

    # instances → configurations (empty)
    instances = SubElement(root, "instances")
    SubElement(instances, "configurations")

    # 格式化输出
    indent(root, space="  ")
    xml_str = tostring(root, encoding="unicode", xml_declaration=False)
    return f'<?xml version="1.0" encoding="utf-8"?>\n{xml_str}'


def _build_interface(interface: Element, program: LadderProgram):
    """构建 PLCopen 接口定义"""
    inputs = [v for v in program.variables if v.address.startswith(("I", "%I"))]
    outputs = [v for v in program.variables if v.address.startswith(("Q", "%Q"))]
    internals = [v for v in program.variables if v.address.startswith(("M", "%M"))]

    classified = set(v.name for v in inputs + outputs + internals)
    for v in program.variables:
        if v.name not in classified:
            inputs.append(v)

    # inputVars
    if inputs:
        iv = SubElement(interface, "inputVars")
        for v in inputs:
            _add_variable(iv, v)

    # outputVars
    if outputs:
        ov = SubElement(interface, "outputVars")
        for v in outputs:
            _add_variable(ov, v)

    # localVars
    if internals:
        lv = SubElement(interface, "localVars")
        for v in internals:
            _add_variable(lv, v)


def _add_variable(parent: Element, v):
    """添加变量定义"""
    var = SubElement(parent, "variable", name=v.name, address=v.address)

    # 数据类型
    vtype = SubElement(var, "type")
    type_map = {
        "Bool": "BOOL", "Byte": "BYTE", "Word": "WORD",
        "DWord": "DWORD", "Int": "INT", "DInt": "DINT",
        "Real": "REAL", "LReal": "LREAL", "String": "STRING",
        "Time": "TIME", "Date": "DATE",
    }
    mapped = type_map.get(v.data_type, v.data_type.upper())
    SubElement(vtype, mapped)

    # 注释
    if v.comment:
        doc = SubElement(var, "documentation")
        xhtml = SubElement(doc, "xhtml", xmlns="http://www.w3.org/1999/xhtml")
        xhtml.text = v.comment


def _build_body(body: Element, program: LadderProgram, block_type: str):
    """构建 PLCopen 程序体（使用 ST 文本表示）"""
    st = SubElement(body, "ST")
    xhtml = SubElement(st, "xhtml", xmlns="http://www.w3.org/1999/xhtml")

    # 将所有 network 的代码组合为 ST 文本
    code_parts = []
    for n in program.networks:
        code_parts.append(f"(* Network {n.number}: {n.title} *)")
        if n.comment:
            code_parts.append(f"(* {n.comment} *)")
        if n.code:
            # 梯形图代码作为注释保留
            code_parts.append(f"(* 梯形图:")
            for line in n.code.split("\n"):
                code_parts.append(f"   {line}")
            code_parts.append("*)")
        code_parts.append("")

    xhtml.text = "\n".join(code_parts)


def _sanitize(title: str) -> str:
    safe = []
    for ch in title[:30]:
        if ch.isalnum() or ch == "_":
            safe.append(ch)
        elif ch in (" ", "-"):
            safe.append("_")
    return "".join(safe).strip("_") or "GeneratedBlock"
