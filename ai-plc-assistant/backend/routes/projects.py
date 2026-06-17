"""项目管理 API"""

from typing import Optional
from fastapi import APIRouter, HTTPException
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
