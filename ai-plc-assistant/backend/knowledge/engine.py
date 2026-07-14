"""知识库引擎 — ChromaDB 向量存储与搜索"""

import logging
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

import chromadb
from chromadb.config import Settings

from .parsers import parse_file, get_file_metadata
from .chunker import chunk_text

logger = logging.getLogger(__name__)


class KnowledgeMigrationRequiredError(RuntimeError):
    """检测到旧集合不兼容，必须先备份并显式迁移。"""


def _create_embedding_function(model_name: str):
    """创建基于 fastembed 的中文嵌入函数（ONNX, 无需 torch）"""
    if os.environ.get("AI_PLC_OFFLINE_TESTING") == "1":
        class OfflineEmbeddingFunction:
            """仅供隔离测试使用的确定性向量，禁止下载模型或访问网络。"""

            def __call__(self, input):
                return self.embed_documents(input)

            def embed_documents(self, input):
                return [[float(len(text) % 97), 1.0, 0.0] for text in input]

            def embed_query(self, input):
                return self.embed_documents(input)

            @staticmethod
            def name():
                return "ai-plc-offline-test-embedding"

            @staticmethod
            def build_from_config(_config):
                return OfflineEmbeddingFunction()

            def is_legacy(self):
                return False

            def default_space(self):
                return "cosine"

            def supported_spaces(self):
                return ["cosine", "l2", "ip"]

            def get_config(self):
                return {}

        return OfflineEmbeddingFunction()
    try:
        from fastembed import TextEmbedding

        class FastEmbedFunction:
            def __init__(self):
                logger.info("加载嵌入模型: %s (首次下载约90MB)", model_name)
                self._model = TextEmbedding(model_name=model_name)

            def __call__(self, input):
                return self.embed_documents(input)

            def embed_documents(self, input):
                return [e.tolist() for e in self._model.embed(input)]

            def embed_query(self, input):
                # ChromaDB passes list of texts, expects list of embeddings
                return [e.tolist() for e in self._model.embed(input)]

            def name(self):
                return "fastembed-" + model_name

        return FastEmbedFunction()
    except ImportError:
        logger.warning("fastembed 未安装, 使用默认英文嵌入模型. 安装: pip install fastembed")
        return None


class KnowledgeEngine:
    """本地知识库引擎，基于 ChromaDB + 中文嵌入模型"""

    def __init__(self, db_path: str, embedding_model: str = ""):
        self.db_path = db_path
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None

    def initialize(self):
        """初始化 ChromaDB 客户端和集合"""
        os.makedirs(self.db_path, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=self.db_path,
            settings=Settings(anonymized_telemetry=False),
        )

        # 创建嵌入函数（中文模型或默认英文）
        ef = _create_embedding_function(self.embedding_model) if self.embedding_model else None

        # 处理维度迁移：旧集合(384维) → 新集合(512维)
        try:
            self._collection = self._client.get_or_create_collection(
                name="plc_knowledge",
                embedding_function=ef,
                metadata={"hnsw:space": "cosine"},
            )
            # 测试维度兼容性
            if self._collection.count() > 0 and ef:
                try:
                    self._collection.query(query_texts=["测试"], n_results=1)
                except Exception:
                    raise KnowledgeMigrationRequiredError(
                        "嵌入维度不匹配；为保护现有知识库已拒绝自动删除。"
                        "请先备份并执行显式迁移。"
                    )
        except Exception as e:
            logger.error("知识库初始化失败: %s", e)
            # 初始化或迁移异常绝不能以删除用户集合作为“恢复”手段。
            self._collection = None
            raise

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

    def index_file(self, file_path: str, original_filename: str = "") -> dict:
        """索引单个文件：解析 → 分块 → 写入向量库

        Returns:
            {"document_id": str, "chunk_count": int, "filename": str}
        """
        # 解析
        text = parse_file(file_path)
        metadata = get_file_metadata(file_path, original_name=original_filename)

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
