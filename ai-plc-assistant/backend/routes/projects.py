"""项目管理 API — CRUD + 工程导入"""

import asyncio
import os
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from security import require_local_session
from search.indexer import SearchIndex
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
async def list_projects(limit: int = Query(50, ge=1, le=200), _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    return {"projects": store.list_all(limit)}


@router.post("", status_code=201)
async def create_project(data: ProjectCreate, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.create(data.name, data.path, data.plc_type, data.tia_version, data.language, data.description)
    return {"project": p}


@router.get("/{pid}")
async def get_project(pid: str, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    store.touch(pid)
    return {"project": p}


@router.put("/{pid}")
async def update_project(pid: str, data: ProjectUpdate, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    p = store.update(pid, **data.model_dump(exclude_none=True))
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": p}


@router.delete("/{pid}")
async def delete_project(pid: str, _actor: str = Depends(require_local_session)):
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")
    if not store.delete(pid):
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"status": "deleted"}


ALLOWED_IMPORT_EXTS = {".ap18", ".ap19", ".ap17", ".zip"}
UPLOAD_CHUNK_BYTES = 64 * 1024
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_ZIP_MEMBERS = 2_000
MAX_ZIP_SINGLE_FILE_BYTES = 50 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 100


def _import_root() -> Path:
    """只在配置的项目根内保留已验证的导入内容。"""
    from config import settings

    if not settings.project_dir:
        raise HTTPException(status_code=503, detail="未配置受控 project_dir，已禁用工程导入")
    try:
        project_root = Path(settings.project_dir).expanduser().resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="受控 project_dir 不可用") from exc
    if not project_root.is_dir():
        raise HTTPException(status_code=503, detail="受控 project_dir 不是目录")
    destination = project_root / ".imports"
    destination.mkdir(parents=True, exist_ok=True)
    return destination.resolve(strict=True)


def _safe_member_path(destination: Path, info: zipfile.ZipInfo) -> Path:
    """验证单个 ZIP 成员，拒绝穿越、绝对路径与符号链接。"""
    filename = info.filename.replace("\\", "/")
    member = PurePosixPath(filename)
    mode = info.external_attr >> 16
    if (
        not filename
        or "\x00" in filename
        or member.is_absolute()
        or any(part in {"", ".", ".."} for part in member.parts)
        or (member.parts and ":" in member.parts[0])
        or stat.S_ISLNK(mode)
    ):
        raise HTTPException(status_code=400, detail="ZIP 包含不安全路径或链接")
    try:
        target = (destination / Path(*member.parts)).resolve()
        target.relative_to(destination)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="ZIP 成员越出导入目录") from exc
    return target


def _safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    """按限额流式解压，不使用不安全的 extractall。"""
    members = archive.infolist()
    if len(members) > MAX_ZIP_MEMBERS:
        raise HTTPException(status_code=413, detail="ZIP 成员数量超过上限")

    total_uncompressed = 0
    validated: list[tuple[zipfile.ZipInfo, Path]] = []
    seen_targets: set[Path] = set()
    seen_file_targets: set[Path] = set()
    implicit_dirs: set[Path] = set()
    for info in members:
        target = _safe_member_path(destination, info)
        if target in seen_targets:
            raise HTTPException(status_code=400, detail="ZIP 含重复路径成员")
        for parent in target.parents:
            if parent in seen_file_targets:
                raise HTTPException(status_code=400, detail="ZIP 文件成员与目录路径冲突")
        seen_targets.add(target)
        if info.is_dir():
            validated.append((info, target))
            continue
        if target in implicit_dirs:
            raise HTTPException(status_code=400, detail="ZIP 成员路径与已有内容冲突")
        seen_file_targets.add(target)
        implicit_dirs.update(target.parents)
        if info.file_size > MAX_ZIP_SINGLE_FILE_BYTES:
            raise HTTPException(status_code=413, detail="ZIP 中存在超过大小上限的文件")
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
            raise HTTPException(status_code=413, detail="ZIP 解压总大小超过上限")
        if info.file_size and (
            info.compress_size <= 0
            or info.file_size / max(info.compress_size, 1) > MAX_ZIP_COMPRESSION_RATIO
        ):
            raise HTTPException(status_code=400, detail="ZIP 压缩比超过安全上限")
        validated.append((info, target))

    for info, target in validated:
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with archive.open(info, "r") as source, target.open("xb") as output:
                while chunk := source.read(UPLOAD_CHUNK_BYTES):
                    written += len(chunk)
                    if written > MAX_ZIP_SINGLE_FILE_BYTES:
                        raise HTTPException(status_code=413, detail="ZIP 成员超过大小上限")
                    output.write(chunk)
        except FileExistsError as exc:
            raise HTTPException(status_code=400, detail="ZIP 成员路径与已有内容冲突") from exc
        if written != info.file_size:
            raise HTTPException(status_code=400, detail="ZIP 成员大小不一致")


def _import_worker(store: ProjectStore, search_engine: SearchIndex, filename: str, tmp_path: str):
    """在线程池中执行解压 + 索引 + 项目记录创建（均为阻塞 IO）。

    失败时自行清理解压目录；成功返回 (extract_dir, project, index_result)。
    """
    import_root = _import_root()
    extract_dir = Path(tempfile.mkdtemp(prefix="plc_import_", dir=import_root))
    try:
        with zipfile.ZipFile(tmp_path, "r") as archive:
            _safe_extract_zip(archive, extract_dir)

        # 复用全局搜索引擎（与 /api/search 同一实例/同一连接），避免对同一
        # search_index.db 另开第二个写连接，造成并发写竞争。
        result = search_engine.index_projects([str(extract_dir)], allowed_root=str(extract_dir))

        ext = Path(filename).suffix.lower()
        tia_version = "V18" if ext == ".ap18" else "V19" if ext == ".ap19" else "V17" if ext == ".ap17" else ""
        project = store.create(
            name=Path(filename).stem,
            path=str(extract_dir),
            tia_version=tia_version,
            description=f"从 {filename} 导入",
        )
        return extract_dir, project, result
    except Exception:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise


@router.post("/import", status_code=201)
async def import_project(
    file: UploadFile = File(...),
    _actor: str = Depends(require_local_session),
):
    """导入 TIA Portal 工程文件 (.ap18/.zip)

    流式接收上传 → 线程内解压 → 复用全局搜索引擎索引 → 创建项目记录
    """
    if store is None:
        raise HTTPException(status_code=503, detail="存储未初始化")

    filename = Path((file.filename or "unknown").replace("\\", "/")).name[:255]
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMPORT_EXTS:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}，仅支持 .ap18/.ap19/.zip")

    tmp_path: str | None = None
    extract_dir: Path | None = None
    imported = False
    try:
        # 先限额流式写入临时归档，避免 await file.read() 把任意输入放进内存。
        uploaded = 0
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_path = tmp.name
            while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                uploaded += len(chunk)
                if uploaded > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="上传文件超过大小上限")
                tmp.write(chunk)

        # 复用全局搜索引擎实例（与 /api/search 同一连接），未初始化时拒绝导入（fail-closed）。
        from routes import search as search_router

        search_engine = search_router.engine
        if search_engine is None:
            raise HTTPException(status_code=503, detail="搜索引擎未初始化")

        # 解压与全量索引均为阻塞 IO，放入线程池执行，避免大量文件时阻塞事件循环。
        extract_dir, project, result = await asyncio.to_thread(
            _import_worker, store, search_engine, filename, tmp_path
        )
        imported = True
        return {
            "project": project,
            "index": {
                "files_scanned": result["files_scanned"],
                "entries_indexed": result["entries_indexed"],
            },
        }
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="文件不是有效的 ZIP 格式")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="导入失败")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if extract_dir is not None and not imported:
            shutil.rmtree(extract_dir, ignore_errors=True)
