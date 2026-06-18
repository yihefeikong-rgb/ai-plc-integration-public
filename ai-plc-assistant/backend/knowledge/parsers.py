"""文件解析器 — 支持 PDF / DOCX / TXT"""

import os
from pathlib import Path


def parse_file(file_path: str) -> str:
    """解析文件为纯文本"""
    ext = Path(file_path).suffix.lower()
    if ext == ".txt":
        return _parse_txt(file_path)
    elif ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext == ".docx":
        return _parse_docx(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def _parse_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _parse_pdf(file_path: str) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")

    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n\n".join(pages)


def _parse_docx(file_path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("请安装 python-docx: pip install python-docx")

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def get_file_metadata(file_path: str, original_name: str = "") -> dict:
    """获取文件元信息"""
    p = Path(file_path)
    return {
        "filename": original_name or p.name,
        "extension": p.suffix.lower(),
        "size_bytes": p.stat().st_size,
        "modified": p.stat().st_mtime,
    }
