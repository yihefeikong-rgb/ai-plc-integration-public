"""PLC 工程搜索 API 路由 — 受控项目根内的索引与搜索。"""

from pathlib import Path

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from security import require_local_session
from search.indexer import SearchIndex

router = APIRouter()

# 搜索引擎实例（由 main.py 注入）
engine: SearchIndex = None  # type: ignore


def set_engine(e: SearchIndex):
    global engine
    engine = e


def _project_root() -> Path:
    """返回已配置的项目根；未配置时拒绝文件系统能力。"""
    from config import settings

    if not settings.project_dir:
        raise HTTPException(status_code=503, detail="未配置受控 project_dir，已禁用工程索引")
    try:
        root = Path(settings.project_dir).expanduser().resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="受控 project_dir 不可用") from exc
    if not root.is_dir():
        raise HTTPException(status_code=503, detail="受控 project_dir 不是目录")
    return root


def _directory_within_root(directory: str, root: Path) -> Path:
    candidate = Path(directory).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="指定项目目录不存在或不可访问") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="目录必须位于受控 project_dir 内") from exc
    if not resolved.is_dir() or resolved.is_symlink():
        raise HTTPException(status_code=400, detail="指定路径不是可扫描目录")
    return resolved


def _public_result(result: dict, root: Path) -> dict:
    """避免将本机绝对路径和无限长度源码直接返回给调用方。"""
    public = dict(result)
    try:
        public["file_path"] = str(Path(str(result["file_path"])).resolve().relative_to(root))
    except (KeyError, OSError, ValueError):
        public["file_path"] = Path(str(result.get("file_path", ""))).name
    public["content"] = str(result.get("content", ""))[:4_000]
    return public


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
    _actor: str = Depends(require_local_session),
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

    root = _project_root()
    return SearchResponse(
        query=result["query"],
        results=[SearchResultItem(**_public_result(r, root)) for r in result["results"]],
        total=result["total"],
    )


@router.post("/index", status_code=201)
async def index_projects(
    directory: str = Query("", description="要扫描的项目目录路径"),
    _actor: str = Depends(require_local_session),
):
    """扫描并索引 PLC 项目目录"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")

    root = _project_root()
    target = _directory_within_root(directory, root) if directory else root
    result = engine.index_projects([str(target)], allowed_root=str(root))
    return {
        "status": "success",
        "files_scanned": result["files_scanned"],
        "entries_indexed": result["entries_indexed"],
    }


@router.get("/types")
async def list_types(_actor: str = Depends(require_local_session)):
    """列出所有可搜索的类型"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    stats = engine.get_stats()
    return {"types": stats.get("by_type", {})}


@router.get("/stats")
async def search_stats(_actor: str = Depends(require_local_session)):
    """搜索引擎统计"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    return engine.get_stats()


@router.delete("/index")
async def clear_index(_actor: str = Depends(require_local_session)):
    """清空搜索索引"""
    if engine is None:
        raise HTTPException(status_code=503, detail="搜索引擎未初始化")
    engine.clear()
    return {"status": "cleared"}
