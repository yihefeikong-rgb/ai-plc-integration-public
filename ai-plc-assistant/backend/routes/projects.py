"""项目管理 API — CRUD + 工程导入"""

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel

from storage.projects import ProjectStore

router = APIRouter()
store: ProjectStore = None  # type: ignore


def set_store(s: ProjectStore):
    global store
    store = s


class ProjectCreate(BaseModel):
    name: str
    path: str = ""
    plc_type: str = "S7-1200"
    tia_version: str = "V18"
    language: str = "SCL"
    description: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    plc_type: Optional[str] = None
    tia_version: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None


@router.get("")
async def list_projects(limit: int = 50):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    return {"projects": store.list_all(limit)}


@router.post("", status_code=201)
async def create_project(data: ProjectCreate):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.create(data.name, data.path, data.plc_type, data.tia_version, data.language, data.description)
    return {"project": p}


@router.get("/{pid}")
async def get_project(pid: str):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    store.touch(pid)
    return {"project": p}


@router.put("/{pid}")
async def update_project(pid: str, data: ProjectUpdate):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.update(pid, **data.model_dump(exclude_none=True))
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": p}


@router.delete("/{pid}")
async def delete_project(pid: str):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    if not store.delete(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"status": "deleted"}


ALLOWED_IMPORT_EXTS = {".ap18", ".ap19", ".ap17", ".zip"}


@router.post("/import", status_code=201)
async def import_project(file: UploadFile = File(...)):
    """导入 TIA Portal 工程文件 (.ap18/.zip)

    解压 ZIP → 扫描 XML/SCL → 索引到搜索引擎 → 创建项目记录
    """
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")

    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMPORT_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 .ap18/.ap19/.zip")

    project_name = Path(filename).stem

    try:
        # 保存到临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 解压
        extract_dir = tempfile.mkdtemp(prefix="plc_import_")
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(extract_dir)

        # 索引解压后的文件
        from search.indexer import SearchIndex
        from storage.app_settings import get_settings_store
        settings = get_settings_store()
        db_path = settings.get("project_search_db", "data/search_index.db") if settings else "data/search_index.db"

        indexer = SearchIndex(db_path=db_path)
        indexer.initialize()
        result = indexer.index_projects([extract_dir])

        # 创建项目记录
        tia_version = "V18" if ".ap18" in ext else "V19" if ".ap19" in ext else "V17" if ".ap17" in ext else ""
        project = store.create(
            name=project_name,
            path=extract_dir,
            tia_version=tia_version,
            description=f"从 {filename} 导入",
        )

        return {
            "project": project,
            "index": {
                "files_scanned": result["files_scanned"],
                "entries_indexed": result["entries_indexed"],
            },
        }
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件不是有效的 ZIP 格式")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
