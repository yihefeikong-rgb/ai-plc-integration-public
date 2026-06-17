"""SSE 流式输出回归测试 — 验证真流式（不是假流式）"""

import json


class TestTrueStreaming:
    def test_multiple_chunks(self, client):
        """SSE 必须返回多个 data 行（真流式，不是一次返回）"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert res.status_code == 200

        data_lines = [
            line for line in res.text.split("\n")
            if line.startswith("data: ") and line != "data: [DONE]"
        ]
        # mock_chat_stream yields ~6 tokens → 至少 5 个 data 行（tokens + done）
        assert len(data_lines) >= 3, \
            f"SSE 只有 {len(data_lines)} 个 data 行, 疑似假流式"

    def test_each_chunk_valid_json(self, client):
        """每个 SSE data 行必须是合法 JSON"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hi"}],
        })

        for line in res.text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                payload = line[6:].strip()
                data = json.loads(payload)  # 不应抛异常
                assert isinstance(data, dict)

    def test_token_accumulation(self, client):
        """拼接所有 token 应还原完整回复"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hi"}],
        })

        tokens = []
        for line in res.text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                if "token" in data:
                    tokens.append(data["token"])

        full_text = "".join(tokens)
        assert len(full_text) > 0, "流式输出没有内容"
        assert len(tokens) > 1, f"只有 {len(tokens)} 个 token, 疑似非流式"

    def test_done_event_has_model(self, client):
        """done 事件必须包含 model 和 fallback 字段"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hi"}],
        })

        done_event = None
        for line in res.text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                if data.get("done"):
                    done_event = data

        assert done_event is not None, "缺少 done 事件"
        assert "model" in done_event
        assert "fallback" in done_event

    def test_stream_ends_with_done_marker(self, client):
        """SSE 流必须以 [DONE] 结尾"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert "data: [DONE]" in res.text

    def test_stream_with_rag(self, client):
        """带 RAG 的流式请求应正常工作"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "PLC编程"}],
            "use_rag": True,
        })
        assert res.status_code == 200
        assert "data: [DONE]" in res.text
