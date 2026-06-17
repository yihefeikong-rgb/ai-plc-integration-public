"""PLC 工程搜索 API 路由 — 索引管理 / 搜索"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from search.indexer import SearchIndex

router = APIRouter()

# 搜索引擎实例（由 main.py 注入）
engine: SearchIndex = None  # type: ignore


def set_engine(e: SearchIndex):
    global engine
    engine = e


class SearchResultItem(BaseModel):
    id: int
    file_path: str
    type: str
    name: str
    block_name: str
    block_type: str
    content: str
    line: int
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total: int


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query("", description="搜索关键词"),
    type_filter: str = Query("", description="按类型过滤: plc_block/variable/network/io_entry"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """搜索 PLC 工程中的块、变量、网络等"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    if not q.strip():
        return SearchResponse(query=q, results=[], total=0)

    if type_filter:
        result = engine.search_by_type(q, type_filter, limit=limit)
    else:
        result = engine.search(q, limit=limit, offset=offset)

    return SearchResponse(
        query=result["query"],
        results=[SearchResultItem(**r) for r in result["results"]],
        total=result["total"],
    )


@router.post("/index", status_code=201)
async def index_projects(
    directory: str = Query("", description="要扫描的项目目录路径"),
):
    """扫描并索引 PLC 项目目录"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")

    dirs = []
    if directory:
        dirs = [directory]
    else:
        from config import settings
        if settings.project_dir:
            dirs = [settings.project_dir]

    if not dirs:
        raise HTTPException(status_code=400, detail="请指定 directory 参数或在配置中设置 project_dir")

    result = engine.index_projects(dirs)
    return {
        "status": "success",
        "files_scanned": result["files_scanned"],
        "entries_indexed": result["entries_indexed"],
    }


@router.get("/types")
async def list_types():
    """列出所有可搜索的类型"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    stats = engine.get_stats()
    return {"types": stats.get("by_type", {})}


@router.get("/stats")
async def search_stats():
    """搜索引擎统计"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    return engine.get_stats()


@router.delete("/index")
async def clear_index():
    """清空搜索索引"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    engine.clear()
    return {"status": "cleared"}
