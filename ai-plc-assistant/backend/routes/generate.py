"""代码生成 API — 自然语言 → SCL/XML/CSV 多格式输出"""

import threading
import time
from collections import deque

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from generator.workflow import GenerationError, generate_ladder, build_prompt
from generator import LadderProgram, Variable, Network
from routes.chat import ALLOWED_MODEL_IDS
from security import require_local_session

router = APIRouter()

# ── 生成端点限流：同一认证主体每分钟最多 GENERATE_MAX_PER_MINUTE 次 ──
GENERATE_MAX_PER_MINUTE = 10
_generate_history: dict[str, deque] = {}
_generate_lock = threading.Lock()


def _check_generate_rate(actor: str) -> None:
    """滑动窗口限流：防止本机进程滥用 LLM 生成端点消耗成本。"""
    now = time.monotonic()
    with _generate_lock:
        history = _generate_history.setdefault(actor, deque())
        while history and now - history[0] >= 60:
            history.popleft()
        if len(history) >= GENERATE_MAX_PER_MINUTE:
            raise HTTPException(status_code=429, detail="生成请求过于频繁，请稍后重试")
        history.append(now)


def _validate_model_id(model_id: str) -> None:
    """与 chat.py 一致：只接受白名单内的模型标识。"""
    if model_id not in ALLOWED_MODEL_IDS:
        raise HTTPException(status_code=400, detail="不支持的模型标识")


class GenerateRequest(BaseModel):
    input: str
    template_id: str = ""
    variables: dict = {}
    context: dict = {}
    model_id: str = "deepseek"


class ExportRequest(BaseModel):
    """从已有的结构化数据导出"""
    title: str = ""
    description: str = ""
    variables: list[dict] = []
    networks: list[dict] = []
    format: str = "scl"  # scl / xml / csv / hmi / alarm / json
    block_type: str = "FB"
    block_name: str = ""


class GenerateResponse(BaseModel):
    title: str
    description: str
    input: str
    text: str
    structured: dict
    mode: str
    ast: dict | None = None
    svg: str | None = None


@router.post("/ladder", response_model=GenerateResponse)
async def generate_ladder_code(req: GenerateRequest, actor: str = Depends(require_local_session)):
    """自然语言 → 梯形图程序（结构化输出）"""
    _check_generate_rate(actor)
    _validate_model_id(req.model_id)
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="请输入程序描述")

    try:
        result = generate_ladder(
            user_input=req.input,
            template_id=req.template_id or None,
            variables=req.variables,
            context=req.context or None,
            model_id=req.model_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail="模型未返回可验证的梯形图，未生成可导出程序") from exc

    return GenerateResponse(**result)


@router.post("/ladder/scl")
async def generate_scl_code(req: GenerateRequest, actor: str = Depends(require_local_session)):
    """自然语言 → SCL 源代码（可直接粘贴到 TIA Portal）"""
    _check_generate_rate(actor)
    _validate_model_id(req.model_id)
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="请输入程序描述")

    try:
        result = generate_ladder(
            user_input=req.input,
            template_id=req.template_id or None,
            variables=req.variables,
            context=req.context or None,
            model_id=req.model_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail="模型未返回可验证的梯形图，未生成可导出程序") from exc

    program = _dict_to_program(result["structured"])

    from generator.scl_generator import generate_scl
    scl = generate_scl(program)
    return {"scl": scl, "mode": result["mode"], "title": result["title"]}


@router.post("/ladder/xml")
async def generate_xml_code(req: GenerateRequest, actor: str = Depends(require_local_session)):
    """自然语言 → PLCopen XML（可导入 TIA Portal）"""
    _check_generate_rate(actor)
    _validate_model_id(req.model_id)
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="请输入程序描述")

    try:
        result = generate_ladder(
            user_input=req.input,
            template_id=req.template_id or None,
            variables=req.variables,
            context=req.context or None,
            model_id=req.model_id,
        )
    except GenerationError as exc:
        raise HTTPException(status_code=502, detail="模型未返回可验证的梯形图，未生成可导出程序") from exc

    program = _dict_to_program(result["structured"])

    from generator.xml_generator import generate_xml
    xml = generate_xml(program)
    return {"xml": xml, "mode": result["mode"], "title": result["title"]}


@router.post("/export")
async def export_code(req: ExportRequest, _actor: str = Depends(require_local_session)):
    """从结构化数据导出为指定格式"""
    program = _dict_to_program({
        "title": req.title,
        "description": req.description,
        "variables": req.variables,
        "networks": req.networks,
    })

    from generator.scl_generator import generate_scl
    from generator.xml_generator import generate_xml
    from generator.export_generator import (
        generate_tag_csv, generate_hmi_tags,
        generate_alarm_list, generate_variable_json,
    )

    exporters = {
        "scl": lambda: generate_scl(program, req.block_type, req.block_name or None),
        "xml": lambda: generate_xml(program, req.block_type, req.block_name or None),
        "csv": lambda: generate_tag_csv(program),
        "hmi": lambda: generate_hmi_tags(program),
        "alarm": lambda: generate_alarm_list(program),
        "json": lambda: generate_variable_json(program),
    }

    exporter = exporters.get(req.format)
    if not exporter:
        raise HTTPException(status_code=400, detail=f"不支持的格式: {req.format}")

    content = exporter()

    # 文件扩展名映射
    ext_map = {"scl": ".scl", "xml": ".xml", "csv": ".csv", "hmi": ".csv", "alarm": ".csv", "json": ".json"}
    mime_map = {"scl": "text/plain", "xml": "application/xml", "csv": "text/csv", "hmi": "text/csv", "alarm": "text/csv", "json": "application/json"}

    return {
        "content": content,
        "format": req.format,
        "filename": f"{req.block_name or 'export'}{ext_map.get(req.format, '.txt')}",
        "mime_type": mime_map.get(req.format, "text/plain"),
    }


def _safe_filename(name: str) -> str:
    """清理用户可控文件名，防止注入 Content-Disposition 响应头。

    RFC 6266 的 quoted-string 不允许 CR/LF、内嵌引号与控制字符；
    这里同时过滤路径分隔符与非法字符，并限制为 ASCII 可见字符，
    避免非 ASCII 文件名在 latin-1 编码的响应头中直接崩溃。
    """
    safe = []
    for ch in name:
        o = ord(ch)
        if 32 <= o <= 126 and ch not in ('"', "\\", "/", ":", "*", "?", "<", ">", "|"):
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip(" ._") or "export"


@router.post("/export/download")
async def download_export(req: ExportRequest, _actor: str = Depends(require_local_session)):
    """导出并直接下载文件"""
    result = await export_code(req, _actor)
    mime = result["mime_type"]
    filename = _safe_filename(result["filename"])
    return PlainTextResponse(
        content=result["content"],
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/prompt")
async def get_generation_prompt(req: GenerateRequest, _actor: str = Depends(require_local_session)):
    """获取 LLM Prompt（调试用）"""
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="请输入程序描述")
    prompt = build_prompt(req.input, req.context or None)
    return {"prompt": prompt}


def _element_to_ascii(elem: dict) -> tuple[str, str]:
    """将结构化元素 dict 转为 (名称, 符号) 两行式 ASCII-LAD-V2 表示。"""
    etype = elem.get("type")
    if etype == "contact":
        return elem.get("name", ""), ("|/|" if elem.get("normally_closed") else "| |")
    if etype == "coil":
        symbol = {"set": "(S)", "reset": "(R)"}.get(elem.get("kind", "normal"), "( )")
        return elem.get("name", ""), symbol
    if etype == "timer":
        return "", f"[{elem.get('timer_type', 'TON')} {elem.get('name', '')} PT={elem.get('pt', '')}]"
    if etype == "counter":
        return "", f"[{elem.get('counter_type', 'CTU')} {elem.get('name', '')} PV={elem.get('pv', 0)}]"
    if etype == "move":
        return "", f"[MOVE IN={elem.get('source', '')} OUT={elem.get('target', '')}]"
    if etype == "comparator":
        return "", f"[CMP {elem.get('op', 'EQ')} {elem.get('a', '')} {elem.get('b', '')}]"
    if etype == "block_call":
        return "", f"[{elem.get('block_type', 'FC')} {elem.get('name', '')}]"
    return "", ""


def _rungs_to_ascii(network: dict) -> str:
    """将结构化 rungs 反序列化为 ASCII-LAD-V2 文本。

    program_to_dict 输出的 networks 只带结构化 rungs（无 code），而
    scl_generator/xml_generator 只消费 Network.code（ASCII 文本）。
    这里把结构化元素重建回 ASCII，避免 /ladder/scl 与 /ladder/xml
    的导出结果静默丢失梯形图逻辑。
    """
    rows: list[str] = []

    for rung in network.get("rungs", []):
        names: list[str] = []
        symbols: list[str] = []
        branch_paths: list[list[dict]] = []

        for elem in rung.get("elements", []):
            if elem.get("type") == "branch":
                paths = elem.get("paths") or []
                if not paths:
                    continue
                # 主路径并入串联序列，其余路径作为 OR 分支单独成行
                for e in paths[0]:
                    name, symbol = _element_to_ascii(e)
                    if symbol:
                        names.append(name)
                        symbols.append(symbol)
                branch_paths.extend(paths[1:])
            else:
                name, symbol = _element_to_ascii(elem)
                if symbol:
                    names.append(name)
                    symbols.append(symbol)

        if not symbols:
            continue

        # 两行式：名称行在上，符号行在下（符号前补 -- 导轨便于 SCL 提取）
        widths = [max(len(names[i]), len(symbols[i])) + 2 for i in range(len(symbols))]
        name_row = "".join(names[i].ljust(widths[i]) for i in range(len(names))).rstrip()
        symbol_row = "--" + "--".join(
            symbols[i].ljust(widths[i] - 2) for i in range(len(symbols))
        ).rstrip()

        if name_row:
            rows.append(name_row)
        rows.append(symbol_row)

        for path in branch_paths:
            path_blocks = [b for b in (_element_to_ascii(e) for e in path) if b[1]]
            if not path_blocks:
                continue
            if any(name for name, _ in path_blocks):
                rows.append("| " + " ".join(name for name, _ in path_blocks if name))
            rows.append("+--" + "--".join(symbol for _, symbol in path_blocks))

    return "\n".join(rows)


def _dict_to_program(data: dict) -> LadderProgram:
    """将字典转换为 LadderProgram 对象"""
    p = LadderProgram(data.get("title", ""), data.get("description", ""))
    for v in data.get("variables", []):
        p.add_variable(
            v.get("address", ""),
            v.get("name", ""),
            v.get("data_type", "Bool"),
            v.get("comment", ""),
        )
    for n in data.get("networks", []):
        code = n.get("code", "")
        if not code and n.get("rungs"):
            # program_to_dict 只输出结构化 rungs，这里反序列化回 ASCII
            # 填入 Network.code，供 scl_generator/xml_generator 消费
            code = _rungs_to_ascii(n)
        p.add_network(
            n.get("number", 0),
            n.get("title", ""),
            code,
            n.get("comment", ""),
        )
    return p
