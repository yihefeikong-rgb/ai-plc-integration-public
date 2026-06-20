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

        # 索引（传入原始文件名，避免显示 tmp_xxx）
        original_name = Path(file.filename or "").name
        result = engine.index_file(tmp_path, original_filename=original_name)
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


@router.get("/code-templates")
async def list_code_templates():
    """列出可用的 SCL 代码模板文件"""
    templates_dir = Path(__file__).parent.parent.parent.parent / "plc-code-templates" / "siemens-scl"
    if not templates_dir.exists():
        return {"templates": []}

    # 英文文件名 → 中文标题映射
    titles = {
        "pump-station": "水泵站多泵控制",
        "cooling-tower": "冷却塔风机控制",
        "packaging-machine": "包装机状态机",
        "sbr-process": "SBR污水处理",
        "cip-system": "CIP清洗系统",
        "pid-control": "PID控制器封装",
        "pid-controller": "PID控制器文档",
        "motor-control": "电机控制文档",
        "batch_counter": "批次计数器",
        "conveyor-with-timer": "传送带定时控制",
        "mixer": "搅拌器控制",
        "tank_level": "水箱液位控制",
        "traffic_light": "十字路口交通灯",
        "conveyor": "传送带文档",
        "material-cart": "料车控制文档",
        "general": "编程通用指南",
        "电梯控制系统": "电梯控制系统",
        "停车场管理系统": "停车场管理系统",
        "楼宇自控HVAC系统": "楼宇自控HVAC系统",
        "冷冻站群控系统": "冷冻站群控系统",
        "VAV变风量末端控制": "VAV变风量末端控制",
        "恒压供水群控": "恒压供水群控",
        "锅炉房热力站控制": "锅炉房热力站控制",
        "智能照明控制": "智能照明控制",
        "新风热回收控制": "新风热回收控制",
    }

    files = []
    for f in sorted(templates_dir.iterdir()):
        if f.suffix in (".scl", ".md") and f.name != "README.md":
            files.append({
                "name": f.stem,
                "type": f.suffix[1:],
                "size": f.stat().st_size,
                "title": titles.get(f.stem, f.stem),
            })
    return {"templates": files}


@router.get("/code-templates/{name}")
async def get_code_template(name: str):
    """获取单个 SCL 代码模板内容"""
    import re as _re
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="无效的模板名称")
    templates_dir = Path(__file__).parent.parent.parent.parent / "plc-code-templates" / "siemens-scl"
    for ext in (".scl", ".md"):
        f = templates_dir / f"{name}{ext}"
        if f.exists():
            content = f.read_text(encoding="utf-8")
            result = {"name": name, "type": ext[1:], "content": content}

            # 对 .scl 文件额外解析中文 IO 表
            if ext == ".scl":
                io_table = {"inputs": [], "outputs": [], "inouts": []}
                current_section = None
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped == "VAR_INPUT":
                        current_section = "inputs"
                        continue
                    if stripped == "VAR_OUTPUT":
                        current_section = "outputs"
                        continue
                    if stripped == "VAR_IN_OUT":
                        current_section = "inouts"
                        continue
                    if stripped == "END_VAR" or stripped == "VAR":
                        current_section = None
                        continue
                    if current_section and stripped:
                        m = _re.match(r'(\w+)\s*:\s*(\w+[.\w]*)\s*;?\s*(?://\s*(.*))?', stripped)
                        if m:
                            io_table[current_section].append({
                                "name": m.group(1),
                                "type": m.group(2),
                                "comment": (m.group(3) or "").strip(),
                            })
                result["io"] = io_table

            return result
    raise HTTPException(status_code=404, detail=f"模板 {name} 不存在")


@router.get("/ladder-templates")
async def list_ladder_templates():
    """列出可用的梯形图 LAD 模板（JSON 格式）"""
    import json as _json
    templates_dir = Path(__file__).parent.parent.parent.parent / "mcp-servers" / "tia-mcp" / "templates"
    if not templates_dir.exists():
        return {"templates": []}

    files = []
    for f in sorted(templates_dir.iterdir()):
        if f.suffix == ".json":
            try:
                data = _json.loads(f.read_text(encoding="utf-8"))
                networks = data.get("networks", [])
                inputs = data.get("interface", {}).get("inputs", [])
                outputs = data.get("interface", {}).get("outputs", [])
                files.append({
                    "name": f.stem,
                    "blockName": data.get("blockName", f.stem),
                    "networkCount": len(networks),
                    "inputCount": len(inputs),
                    "outputCount": len(outputs),
                    "networks": [n.get("title", "") for n in networks],
                })
            except Exception:
                pass
    return {"templates": files}


@router.get("/ladder-templates/{name}")
async def get_ladder_template(name: str):
    """获取单个梯形图模板完整 JSON + 文本化展示"""
    import json as _json
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="无效的模板名称")
    templates_dir = Path(__file__).parent.parent.parent.parent / "mcp-servers" / "tia-mcp" / "templates"
    f = templates_dir / f"{name}.json"
    if not f.exists():
        raise HTTPException(status_code=404, detail=f"梯形图模板 {name} 不存在")

    data = _json.loads(f.read_text(encoding="utf-8"))

    # 生成文本化展示
    text_lines = []
    text_lines.append(f"功能块: {data.get('blockName', name)}")
    text_lines.append("")

    # 构建 operand→中文名 映射（网络元素展示用）
    cn_map = {}
    iface = data.get("interface", {})
    for sig in iface.get("inputs", []):
        cn_map[sig["name"]] = sig.get("comment", sig["name"])
    for sig in iface.get("outputs", []):
        cn_map[sig["name"]] = sig.get("comment", sig["name"])
    for sig in iface.get("local", []):
        cn_map[sig["name"]] = sig.get("comment", sig["name"])

    # IO 表（中文名为主）
    if iface.get("inputs"):
        text_lines.append("【输入】")
        for sig in iface["inputs"]:
            addr = sig.get("address", "")
            cname = sig.get("comment", sig["name"])
            text_lines.append(f"  {cname} ({sig['name']}) : {sig['type']}  {addr}")
    if iface.get("outputs"):
        text_lines.append("【输出】")
        for sig in iface["outputs"]:
            addr = sig.get("address", "")
            cname = sig.get("comment", sig["name"])
            text_lines.append(f"  {cname} ({sig['name']}) : {sig['type']}  {addr}")
    if iface.get("local"):
        text_lines.append("【中间变量】")
        for sig in iface["local"]:
            cname = sig.get("comment", sig["name"])
            text_lines.append(f"  {cname} ({sig['name']}) : {sig['type']}")

    text_lines.append("")

    # 网络文本化
    element_map = {
        "normally_open": "NO",
        "normally_closed": "NC",
        "coil": "( )",
        "coil_set": "(S)",
        "coil_reset": "(R)",
    }
    for i, net in enumerate(data.get("networks", []), 1):
        title = net.get("title", f"网络{i}")
        comment = net.get("comment", "")
        text_lines.append(f"网络{i}: {title}")
        if comment:
            text_lines.append(f"  // {comment}")
        elements = net.get("elements", [])
        parts = []
        for el in elements:
            etype = el.get("type", "")
            operand = el.get("operand", "?")
            symbol = element_map.get(etype, etype)
            cn_operand = cn_map.get(operand, operand)
            if etype in ("normally_open", "normally_closed"):
                parts.append(f"[{cn_operand} {symbol}]")
            else:
                parts.append(f"({cn_operand} {symbol})")
        text_lines.append(f"  {' ── '.join(parts)}")
        text_lines.append("")

    return {
        "name": name,
        "data": data,
        "text": "\n".join(text_lines),
    }
