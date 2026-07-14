"""代码生成 API — 自然语言 → SCL/XML/CSV 多格式输出"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from generator.workflow import GenerationError, generate_ladder, build_prompt
from generator import LadderProgram, Variable, Network
from security import require_local_session

router = APIRouter()


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
async def generate_ladder_code(req: GenerateRequest, _actor: str = Depends(require_local_session)):
    """自然语言 → 梯形图程序（结构化输出）"""
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
async def generate_scl_code(req: GenerateRequest, _actor: str = Depends(require_local_session)):
    """自然语言 → SCL 源代码（可直接粘贴到 TIA Portal）"""
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
async def generate_xml_code(req: GenerateRequest, _actor: str = Depends(require_local_session)):
    """自然语言 → PLCopen XML（可导入 TIA Portal）"""
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


@router.post("/export/download")
async def download_export(req: ExportRequest, _actor: str = Depends(require_local_session)):
    """导出并直接下载文件"""
    result = await export_code(req, _actor)
    mime = result["mime_type"]
    return PlainTextResponse(
        content=result["content"],
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
    )


@router.post("/prompt")
async def get_generation_prompt(req: GenerateRequest, _actor: str = Depends(require_local_session)):
    """获取 LLM Prompt（调试用）"""
    if not req.input.strip():
        raise HTTPException(status_code=400, detail="请输入程序描述")
    prompt = build_prompt(req.input, req.context or None)
    return {"prompt": prompt}


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
        p.add_network(
            n.get("number", 0),
            n.get("title", ""),
            n.get("code", ""),
            n.get("comment", ""),
        )
    return p
