"""文本分块器 — 将长文本分割为可索引的块"""

import re
from typing import List


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
) -> List[dict]:
    """将文本分割为带元信息的块列表

    Args:
        text: 要分割的文本
        chunk_size: 每块目标字符数
        chunk_overlap: 块间重叠字符数

    Returns:
        [{"text": str, "chunk_index": int}, ...]
    """
    if not text.strip():
        return []

    # 先按段落分割
    paragraphs = _split_paragraphs(text)
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        # 单一段落超过块大小 → 按句子拆分后独立成块
        if para_len > chunk_size:
            if current:
                chunks.append(_join_chunk(current))
                current = []
                current_len = 0
            for sentence_chunk in _split_large_paragraph(para, chunk_size, chunk_overlap):
                chunks.append(sentence_chunk)
            continue

        # 累积段落直到达到块大小
        if current_len + para_len > chunk_size and current:
            chunks.append(_join_chunk(current))
            # 保留 overlap 段
            overlap_texts = _get_overlap(current, chunk_overlap)
            current = overlap_texts
            current_len = sum(len(t) for t in overlap_texts)

        current.append(para)
        current_len += para_len

    if current:
        chunks.append(_join_chunk(current))

    # 添加索引
    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i

    return chunks


def _split_paragraphs(text: str) -> List[str]:
    """按空行分割段落，过滤空段"""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def _split_large_paragraph(text: str, chunk_size: int, overlap: int) -> List[dict]:
    """将超长段落按句号/换行切割为多个块"""
    # 优先按句号、换行分割
    sentences = re.split(r"(?<=[。！？.!?\n])\s*", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        # 没有可用的句子边界，按字符切割
        return [{"text": text[i:i + chunk_size]} for i in range(0, len(text), chunk_size - overlap)]

    chunks = []
    current = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len > chunk_size and current:
            chunks.append({"text": "".join(current)})
            overlap_texts = _get_overlap(current, overlap)
            current = overlap_texts
            current_len = sum(len(t) for t in overlap_texts)
        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append({"text": "".join(current)})

    return chunks


def _join_chunk(texts: List[str]) -> dict:
    return {"text": "\n".join(texts)}


def _get_overlap(texts: List[str], overlap_chars: int) -> List[str]:
    """从末尾收集足够字符作为重叠"""
    result = []
    total = 0
    for t in reversed(texts):
        result.insert(0, t)
        total += len(t)
        if total >= overlap_chars:
            break
    return result
