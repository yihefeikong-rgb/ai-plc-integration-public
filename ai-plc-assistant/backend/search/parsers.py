"""PLC 文件解析器 — 从 XML/SCL/CSV 中提取结构化信息"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional


def parse_file(file_path: str) -> List[dict]:
    """解析 PLC 文件，提取可索引条目

    Returns:
        [{"type": str, "name": str, "content": str, "line": int, ...}, ...]
    """
    ext = Path(file_path).suffix.lower()

    try:
        if ext == ".xml":
            return _parse_xml(file_path)
        elif ext == ".scl":
            return _parse_scl(file_path)
        elif ext == ".csv":
            return _parse_csv(file_path)
        elif ext in (".awl",):
            return _parse_awl(file_path)
        else:
            # 通用文本解析
            return _parse_generic(file_path)
    except Exception as e:
        return [{"type": "error", "name": "", "content": f"解析失败: {e}", "line": 0}]


# ---- XML 解析 ----

def _parse_xml(file_path: str) -> List[dict]:
    entries = []
    tree = ET.parse(file_path)
    root = tree.getroot()

    # 去除命名空间
    ns = _strip_ns(root.tag)
    is_block = "PlcBlock" in ns or "Block" in ns

    if is_block:
        entries.extend(_parse_plc_block_xml(root, file_path))
    else:
        # 通用 XML: 提取所有文本内容
        text_content = " ".join(root.itertext()).strip()
        if text_content:
            entries.append({
                "type": "xml_content",
                "name": Path(file_path).stem,
                "content": text_content[:2000],
                "line": 0,
            })

    return entries


def _parse_plc_block_xml(root: ET.Element, file_path: str) -> List[dict]:
    entries = []
    name = Path(file_path).stem
    block_type = "Block"
    title = ""

    # 遍历 AttributeList
    for attr_list in root.iter("{*}AttributeList"):
        for child in attr_list:
            tag = _strip_ns(child.tag)
            text = (child.text or "").strip()
            if tag == "Name":
                name = text
            elif tag == "BlockType":
                block_type = text
            elif tag == "Title" or tag == "Comment":
                title = text

    # 添加块级条目
    entries.append({
        "type": "plc_block",
        "name": name,
        "block_type": block_type,
        "content": f"{block_type} \"{name}\" - {title}" if title else f"{block_type} \"{name}\"",
        "line": 0,
    })

    # 提取变量成员
    for member in root.iter("{*}PlcBlockLocalMember"):
        entries.append(_parse_member(member, name, block_type))

    for member in root.iter("{*}Member"):
        entries.append(_parse_member(member, name, block_type))

    return entries


def _parse_member(member: ET.Element, block_name: str, block_type: str) -> dict:
    var_name = ""
    var_type = ""
    comment = ""
    section = ""

    for attr_list in member.iter("{*}AttributeList"):
        for child in attr_list:
            tag = _strip_ns(child.tag)
            text = (child.text or "").strip()
            if tag == "Name":
                var_name = text
            elif tag == "DataType":
                var_type = text
            elif tag == "Comment":
                comment = text
            elif tag == "SectionType":
                section = text

    content_parts = [f"{var_name}: {var_type}"]
    if comment:
        content_parts.append(f"// {comment}")
    if section:
        content_parts.append(f"[{section}]")

    return {
        "type": "variable",
        "name": var_name,
        "block_name": block_name,
        "block_type": block_type,
        "content": " | ".join(content_parts),
        "line": 0,
    }


# ---- SCL 解析 ----

SCL_PATTERNS = {
    "function_block": re.compile(
        r'FUNCTION_BLOCK\s+"?([^"\s]+)"?',
        re.IGNORECASE,
    ),
    "function": re.compile(
        r'FUNCTION\s+"?([^"\s]+)"?\s*:\s*(\w+)',
        re.IGNORECASE,
    ),
    "data_block": re.compile(
        r'DATA_BLOCK\s+"?([^"\s]+)"?',
        re.IGNORECASE,
    ),
    "organization_block": re.compile(
        r'ORGANIZATION_BLOCK\s+"?([^"\s]+)"?',
        re.IGNORECASE,
    ),
    "variable": re.compile(
        r'^\s+(\w+)\s*:\s*(\w[\w.]*)\s*;?\s*(?://\s*(.*))?$',
        re.MULTILINE,
    ),
    "network": re.compile(
        r'NETWORK\s*\n?\s*TITLE\s*=\s*["\']?(.*?)["\']?$',
        re.MULTILINE | re.IGNORECASE,
    ),
    "comment": re.compile(r'//\s*(.*)'),
}


def _parse_scl(file_path: str) -> List[dict]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    entries = []

    # 检测块类型和名称
    block_name = Path(file_path).stem
    block_type = "SCL"

    for key, pattern in [
        ("function_block", SCL_PATTERNS["function_block"]),
        ("function", SCL_PATTERNS["function"]),
        ("data_block", SCL_PATTERNS["data_block"]),
        ("organization_block", SCL_PATTERNS["organization_block"]),
    ]:
        m = pattern.search(text)
        if m:
            block_name = m.group(1)
            block_type = {
                "function_block": "FB", "function": "FC",
                "data_block": "DB", "organization_block": "OB",
            }.get(key, "SCL")
            break

    # 块级条目
    entries.append({
        "type": "plc_block",
        "name": block_name,
        "block_type": block_type,
        "content": f"{block_type} \"{block_name}\"",
        "line": 0,
    })

    # 提取变量
    for m in SCL_PATTERNS["variable"].finditer(text):
        vname = m.group(1)
        vtype = m.group(2)
        vcomment = m.group(3) or ""
        content = f"{vname}: {vtype}"
        if vcomment:
            content += f" // {vcomment}"
        entries.append({
            "type": "variable",
            "name": vname,
            "block_name": block_name,
            "block_type": block_type,
            "content": content,
            "line": text[:m.start()].count("\n") + 1,
        })

    # 提取 NETWORK 标题
    for m in SCL_PATTERNS["network"].finditer(text):
        title = m.group(1).strip()
        entries.append({
            "type": "network",
            "name": title,
            "block_name": block_name,
            "block_type": block_type,
            "content": f"NETWORK: {title}",
            "line": text[:m.start()].count("\n") + 1,
        })

    return entries


# ---- CSV 解析 ----

def _parse_csv(file_path: str) -> List[dict]:
    entries = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    headers = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        parts = [p.strip() for p in line.split(",")]

        if not headers:
            headers = parts
            continue

        if len(parts) >= 2:
            row = dict(zip(headers, parts + [""] * (len(headers) - len(parts))))
            content = " | ".join(f"{k}={v}" for k, v in row.items())
            entries.append({
                "type": "io_entry",
                "name": row.get("name", row.get("Name", parts[0])),
                "content": content,
                "line": i + 1,
            })

    return entries


# ---- AWL/STL 解析 ----

def _parse_awl(file_path: str) -> List[dict]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    entries = []
    lines = text.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue

        # 检测块定义
        if re.match(r'(FUNCTION|FUNCTION_BLOCK|DATA_BLOCK|ORGANIZATION_BLOCK)\b', stripped, re.IGNORECASE):
            entries.append({
                "type": "plc_block",
                "name": Path(file_path).stem,
                "content": stripped,
                "line": i + 1,
            })

    return entries


# ---- 通用文本解析 ----

def _parse_generic(file_path: str) -> List[dict]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    lines = text.split("\n")
    entries = []

    for i, line in enumerate(lines[:200]):  # 最多处理 200 行
        stripped = line.strip()
        if stripped and not stripped.startswith(("//", "#", ";")):
            entries.append({
                "type": "generic",
                "name": Path(file_path).stem,
                "content": stripped[:500],
                "line": i + 1,
            })

    return entries


# ---- 辅助 ----

def _strip_ns(tag: str) -> str:
    """去除 XML 标签的命名空间"""
    return tag.split("}")[-1] if "}" in tag else tag
