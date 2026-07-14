"""PLC 工程目录扫描器 — 仅扫描经授权的本地项目根。"""

import os
from pathlib import Path
from typing import List, Optional

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

MAX_SCAN_FILES = 10_000
MAX_FILE_BYTES = 10 * 1024 * 1024


def _resolve_existing_directory(path: Path) -> Optional[Path]:
    try:
        if path.is_symlink() or not path.is_dir():
            return None
        return path.resolve(strict=True)
    except OSError:
        return None


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def scan_directory(
    directory: str,
    recursive: bool = True,
    *,
    allowed_root: str | None = None,
    max_files: int = MAX_SCAN_FILES,
) -> List[dict]:
    """扫描一个已授权目录，跳过符号链接、超大文件与超出根的路径。

    ``allowed_root`` 为 None 时只允许扫描传入目录本身；API 调用必须传入
    配置的项目根，避免用户借由符号链接或绝对路径扩大读取范围。
    """
    base = _resolve_existing_directory(Path(directory).expanduser())
    if base is None:
        return []

    root_source = Path(allowed_root).expanduser() if allowed_root else base
    root = _resolve_existing_directory(root_source)
    if root is None or not _is_within(base, root):
        return []

    results: List[dict] = []
    walker = os.walk(base, topdown=True, followlinks=False)
    for current_dir, dir_names, file_names in walker:
        current = Path(current_dir)
        # 在进入子目录前剔除排除目录和所有符号链接目录。
        dir_names[:] = [
            name for name in dir_names
            if name not in EXCLUDE_DIRS and not (current / name).is_symlink()
        ]

        for name in file_names:
            if len(results) >= max_files:
                return results
            candidate = current / name
            try:
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                resolved = candidate.resolve(strict=True)
                if not _is_within(resolved, root):
                    continue
                ext = resolved.suffix.lower()
                if ext not in PLC_FILE_EXTENSIONS:
                    continue
                size = resolved.stat().st_size
            except OSError:
                continue
            if size > MAX_FILE_BYTES:
                continue
            results.append({
                "path": str(resolved),
                "ext": ext,
                "type": PLC_FILE_EXTENSIONS[ext],
                "size": size,
            })

        if not recursive:
            break

    return results


def scan_projects(
    project_dirs: List[str],
    *,
    allowed_root: str | None = None,
    max_files: int = MAX_SCAN_FILES,
) -> List[dict]:
    """扫描多个受控项目目录，合并并限制总文件数。"""
    all_files = []
    seen = set()
    for directory in project_dirs:
        remaining = max_files - len(all_files)
        if remaining <= 0:
            break
        for file_info in scan_directory(
            directory,
            allowed_root=allowed_root,
            max_files=remaining,
        ):
            if file_info["path"] not in seen:
                seen.add(file_info["path"])
                all_files.append(file_info)
    return all_files


def is_plc_related_file(file_path: str) -> bool:
    """快速判断文件是否与 PLC 相关。"""
    return Path(file_path).suffix.lower() in PLC_FILE_EXTENSIONS
