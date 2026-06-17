"""PLC 工程目录扫描器 — 递归扫描目录，识别相关文件"""

import os
from pathlib import Path
from typing import List, Generator

# 支持的扩展名
PLC_FILE_EXTENSIONS = {
    ".xml": "xml",
    ".scl": "scl",
    ".csv": "csv",
    ".udt": "udt",     # TIA Portal UDT export
    ".ap18": "ap18",   # TIA Portal V18 project (ZIP)
    ".ap19": "ap19",   # TIA Portal V19 project (ZIP)
    ".awl": "awl",     # AWL/STL source
}

# 扫描时排除的目录
EXCLUDE_DIRS = {
    ".git", "__pycache__", "node_modules", "venv", ".venv",
    "data", "dist", "build", ".claude", ".vscode", ".idea",
}

# 需要扫描的内容关键词（用于快速判断）
PLC_KEYWORDS = [
    "TIA Portal", "SIMATIC", "S7-1200", "S7-1500",
    "FUNCTION_BLOCK", "FUNCTION", "ORGANIZATION_BLOCK",
    "DATA_BLOCK", "NETWORK", "TITLE", "VAR_INPUT",
    "PLC", "AUTO", "DB", "FC", "FB", "OB",
]


def scan_directory(directory: str, recursive: bool = True) -> List[dict]:
    """扫描目录，返回 PLC 相关文件列表

    Returns:
        [{"path": str, "ext": str, "type": str, "size": int}, ...]
    """
    results = []
    base = Path(directory)
    if not base.exists():
        return results

    for f in base.rglob("*") if recursive else base.glob("*"):
        if not f.is_file():
            continue
        # 跳过排除目录
        if any(excl in f.parts for excl in EXCLUDE_DIRS):
            continue
        # 跳过大型文件（>10MB 的非 XML 文件不太可能是 PLC 源码）
        if f.suffix.lower() != ".xml" and f.stat().st_size > 10 * 1024 * 1024:
            continue
        ext = f.suffix.lower()
        if ext in PLC_FILE_EXTENSIONS:
            results.append({
                "path": str(f.absolute()),
                "ext": ext,
                "type": PLC_FILE_EXTENSIONS[ext],
                "size": f.stat().st_size,
            })

    return results


def scan_projects(project_dirs: List[str]) -> List[dict]:
    """扫描多个项目目录，合并文件列表"""
    all_files = []
    seen = set()
    for directory in project_dirs:
        for f in scan_directory(directory):
            if f["path"] not in seen:
                seen.add(f["path"])
                all_files.append(f)
    return all_files


def is_plc_related_file(file_path: str) -> bool:
    """快速判断文件是否与 PLC 相关"""
    ext = Path(file_path).suffix.lower()
    if ext in PLC_FILE_EXTENSIONS:
        return True
    return False
