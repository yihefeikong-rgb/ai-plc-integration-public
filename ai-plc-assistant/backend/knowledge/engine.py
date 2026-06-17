"""知识库引擎 — ChromaDB 向量存储与搜索"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings

from .parsers import parse_file, get_file_metadata
from .chunker import chunk_text


class KnowledgeEngine:
    """本地知识库引擎，基于 ChromaDB + 本地嵌入模型"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._client = None
        self._collection = None

    def initialize(self):
        """初始化 ChromaDB 客户端和集合"""
        os.makedirs(self.db_path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False),
        )
        # 使用默认的 all-MiniLM-L6-v2 嵌入（自动下载）
        self._collection = self._client.get_or_create_collection(
            name="plc_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        return self

    @property
    def collection(self):
        if self._collection is None:
            self.initialize()
        return self._collection

    @property
    def client(self):
        if self._client is None:
            self.initialize()
        return self._client

    # ---- Indexing ----

    def index_file(self, file_path: str) -> dict:
        """索引单个文件：解析 → 分块 → 写入向量库

        Returns:
            {"document_id": str, "chunk_count": int, "filename": str}
        """
        # 解析
        text = parse_file(file_path)
        metadata = get_file_metadata(file_path)

        # 分块
        chunks = chunk_text(text)
        if not chunks:
            return {"document_id": "", "chunk_count": 0, "filename": metadata["filename"]}

        # 生成文档ID
        doc_id = str(uuid.uuid4())

        # 准备 ChromaDB 数据
        ids = [f"{doc_id}_{c['chunk_index']}" for c in chunks]
        documents = [c["text"] for c in chunks]
        metadatas = [
            {
                "document_id": doc_id,
                "filename": metadata["filename"],
                "extension": metadata["extension"],
                "chunk_index": c["chunk_index"],
                "total_chunks": len(chunks),
            }
            for c in chunks
        ]

        # 写入
        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        return {
            "document_id": doc_id,
            "chunk_count": len(chunks),
            "filename": metadata["filename"],
        }

    def delete_document(self, document_id: str) -> bool:
        """按 document_id 删除所有相关块"""
        # ChromaDB 没有按元数据批量删除的API
        # 需要先查出所有匹配的 id，然后按 id 删除
        all_ids = self.collection.get(limit=10_000_000)["ids"]
        to_delete = [i for i in all_ids if i.startswith(f"{document_id}_")]
        if to_delete:
            self.collection.delete(ids=to_delete)
            return True
        return False

    def list_documents(self) -> List[dict]:
        """列出所有已索引的去重文档列表"""
        all_meta = self.collection.get(limit=10_000_000)["metadatas"]
        seen = {}
        for m in all_meta:
            if m and m["document_id"] not in seen:
                seen[m["document_id"]] = {
                    "document_id": m["document_id"],
                    "filename": m["filename"],
                    "chunk_count": m["total_chunks"],
                }
        return list(seen.values())

    def get_stats(self) -> dict:
        """获取知识库统计"""
        count = self.collection.count()
        docs = self.list_documents()
        return {
            "total_chunks": count,
            "total_documents": len(docs),
            "documents": docs,
        }

    def clear(self):
        """清空知识库"""
        try:
            self.client.delete_collection("plc_knowledge")
        except ValueError:
            pass
        self._collection = self.client.get_or_create_collection(name="plc_knowledge")

    # ---- Search ----

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """向量相似度搜索

        Returns:
            [{"text": str, "score": float, "filename": str, "chunk_index": int}, ...]
        """
        if not query.strip():
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k, 100),
        )

        output = []
        for i in range(len(results["ids"][0])):
            output.append({
                "text": results["documents"][0][i],
                "score": round((1 - results["distances"][0][i]) * 100, 1),
                "filename": results["metadatas"][0][i]["filename"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
            })

        return output
