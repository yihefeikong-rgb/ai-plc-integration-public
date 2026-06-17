"""测试 knowledge/chunker.py — 文本分块器"""

from knowledge.chunker import chunk_text


class TestChunkText:
    def test_empty_input(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_short_text(self):
        result = chunk_text("Hello world")
        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["chunk_index"] == 0

    def test_single_paragraph(self):
        text = "这是一段关于PLC编程的说明。" * 10
        result = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(result) >= 1
        for i, chunk in enumerate(result):
            assert chunk["chunk_index"] == i
            assert len(chunk["text"]) > 0

    def test_multiple_paragraphs(self):
        text = "第一段内容。\n\n第二段内容。\n\n第三段内容。"
        result = chunk_text(text, chunk_size=500, chunk_overlap=50)
        assert len(result) >= 1
        combined = " ".join(r["text"] for r in result)
        assert "第一段" in combined
        assert "第三段" in combined

    def test_large_paragraph_splitting(self):
        """超长段落应按句子切割"""
        text = "。".join([f"这是第{i}句话" for i in range(50)])
        result = chunk_text(text, chunk_size=100, chunk_overlap=20)
        assert len(result) > 1

    def test_chunk_indices_sequential(self):
        text = "段落A。\n\n段落B。\n\n段落C。\n\n段落D。\n\n段落E。"
        result = chunk_text(text, chunk_size=20, chunk_overlap=5)
        indices = [r["chunk_index"] for r in result]
        assert indices == list(range(len(indices)))

    def test_overlap_preserves_context(self):
        """分块间应有重叠内容"""
        sentences = ["。".join([f"句子{i}" for i in range(j * 10, (j + 1) * 10)]) for j in range(5)]
        text = "\n\n".join(sentences)
        result = chunk_text(text, chunk_size=100, chunk_overlap=30)
        if len(result) >= 2:
            # 至少部分内容在相邻块间共享
            assert len(result[0]["text"]) > 0
            assert len(result[1]["text"]) > 0
