"""知识库 API 路由 — 导入 / 搜索 / 管理"""

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from pydantic import BaseModel

from knowledge.engine import KnowledgeEngine

router = APIRouter()

# 存储引擎实例（由 main.py 初始化时注入）
engine: KnowledgeEngine = None  # type: ignore


def set_engine(k: KnowledgeEngine):
    global engine
    engine = k


class SearchResult(BaseModel):
    text: str
    score: float
    filename: str
    chunk_index: int


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


class StatsResponse(BaseModel):
    total_chunks: int
    total_documents: int
    documents: list[dict]


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/import", status_code=201)
async def import_document(file: UploadFile = File(...)):
    """导入文档到知识库（PDF / DOCX / TXT）"""
    if engine is None:
        raise HTTPException(status_code=503, detail="知识库引擎未初始化")

    # 验证文件类型
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 PDF/DOCX/TXT",
        )

    # 保存到临时文件
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 索引
        result = engine.index_file(tmp_path)
        return {
            "document_id": result["document_id"],
            "filename": result["filename"],
            "chunk_count": result["chunk_count"],
            "status": "success",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/search", response_model=SearchResponse)
async def search_knowledge(
    q: str = Query("", description="搜索关键词"),
    limit: int = Query(5, description="返回结果数", ge=1, le=50),
):
    """在知识库中搜索相关内容"""
    if engine is None:
        raise HTTPException(status_code=503, detail="知识库引擎未初始化")
    if not q.strip():
        return SearchResponse(query=q, results=[], total=0)

    results = engine.search(q, top_k=limit)
    return SearchResponse(
        query=q,
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )


@router.get("/documents")
async def list_documents():
    """列出所有已索引的文档"""
    if engine is None:
        raise HTTPException(status_code=503, detail="知识库引擎未初始化")
    return {"documents": engine.list_documents()}


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """删除指定文档及其所有块"""
    if engine is None:
        raise HTTPException(status_code=503, detail="知识库引擎未初始化")
    ok = engine.delete_document(document_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"文档 {document_id} 不存在")
    return {"status": "deleted", "document_id": document_id}


@router.get("/status", response_model=StatsResponse)
async def knowledge_status():
    """知识库统计信息"""
    if engine is None:
        raise HTTPException(status_code=503, detail="知识库引擎未初始化")
    stats = engine.get_stats()
    return StatsResponse(**stats)
