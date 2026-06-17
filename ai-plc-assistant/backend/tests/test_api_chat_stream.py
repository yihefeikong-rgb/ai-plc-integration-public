"""API 测试 — /api/chat/stream SSE"""

import json


class TestChatStream:
    def test_stream_basic(self, client):
        """SSE 流式端点应返回 token 事件"""
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        # 解析 SSE 事件
        tokens = []
        done_event = None
        for line in res.text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                data = json.loads(line[6:])
                if "token" in data:
                    tokens.append(data["token"])
                if data.get("done"):
                    done_event = data

        assert len(tokens) > 0
        assert done_event is not None
        assert done_event["model"] == "deepseek"
        assert done_event["fallback"] is False

    def test_stream_empty_messages(self, client):
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [],
        })
        assert res.status_code == 400

    def test_stream_has_done_marker(self, client):
        res = client.post("/api/chat/stream", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "hi"}],
        })
        assert "data: [DONE]" in res.text
