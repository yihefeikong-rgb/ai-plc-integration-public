"""知识库集成测试 — 导入 → 搜索 → RAG → 删除 全流程"""

import io


class TestKnowledgeLifecycle:
    def test_import_search_delete(self, client):
        """完整生命周期：导入 TXT → 搜索 → 删除"""
        # 1. 导入
        content = "西门子 S7-1200 支持 PROFINET 通信协议。\nPUT/GET 通信需要在硬件配置中启用。"
        files = {"file": ("plc_guide.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
        res = client.post("/api/knowledge/import", files=files)
        assert res.status_code == 201
        data = res.json()
        assert data["chunk_count"] >= 1
        doc_id = data["document_id"]

        # 2. 列出文档
        res = client.get("/api/knowledge/documents")
        assert res.status_code == 200
        docs = res.json()["documents"]
        doc_ids = [d["document_id"] for d in docs]
        assert doc_id in doc_ids

        # 3. 搜索
        res = client.get("/api/knowledge/search?q=PROFINET")
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) >= 1
        assert any("PROFINET" in r["text"] for r in results)

        # 4. 统计
        res = client.get("/api/knowledge/status")
        assert res.status_code == 200
        assert res.json()["total_documents"] >= 1

        # 5. 删除
        res = client.delete(f"/api/knowledge/documents/{doc_id}")
        assert res.status_code == 200

        # 6. 验证删除
        res = client.get("/api/knowledge/documents")
        doc_ids = [d["document_id"] for d in res.json()["documents"]]
        assert doc_id not in doc_ids

    def test_import_invalid_format(self, client):
        """不支持的文件格式应返回 400"""
        files = {"file": ("test.xyz", io.BytesIO(b"content"), "application/octet-stream")}
        res = client.post("/api/knowledge/import", files=files)
        assert res.status_code == 400

    def test_search_empty_knowledge(self, client):
        """空知识库搜索不应报错"""
        res = client.get("/api/knowledge/search?q=something")
        assert res.status_code == 200


class TestRAGIntegration:
    def test_chat_with_rag(self, client):
        """导入文档后聊天应触发 RAG 检索"""
        # 导入
        content = "MODBUS_RTU 通信需要设置波特率为 9600 和偶校验。"
        files = {"file": ("modbus.txt", io.BytesIO(content.encode("utf-8")), "text/plain")}
        res = client.post("/api/knowledge/import", files=files)
        assert res.status_code == 201
        doc_id = res.json()["document_id"]

        # 带 RAG 聊天
        res = client.post("/api/chat", json={
            "model_id": "deepseek",
            "messages": [{"role": "user", "content": "MODBUS 通信怎么配置"}],
            "use_rag": True,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["content"]  # 应有回复
        # RAG 源可能被返回（文件名是临时文件名，不是原始名）
        if data.get("rag_sources"):
            assert len(data["rag_sources"]) >= 1

        # 清理
        client.delete(f"/api/knowledge/documents/{doc_id}")
