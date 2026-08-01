"""Prompt 模板管理 — 分类CRUD，JSON持久化"""

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security import require_local_session

router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PROMPTS_FILE = os.environ.get("PROMPTS_FILE", os.path.join(DATA_DIR, "prompts.json"))
DATA_DIR = os.path.dirname(PROMPTS_FILE)


# ---- 数据模型 ----

class TemplateVariable(BaseModel):
    name: str
    label: str
    default: str = ""
    type: str = "string"


class Template(BaseModel):
    id: str
    name: str
    category: str
    description: str = ""
    content: str = ""
    variables: list[TemplateVariable] = []
    created_at: float = 0
    updated_at: float = 0


class TemplateCreate(BaseModel):
    name: str
    category: str
    description: str = ""
    content: str = ""
    variables: list[TemplateVariable] = []


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[list[TemplateVariable]] = None


# ---- 持久化 ----

def _load_all() -> list[dict]:
    if not os.path.exists(PROMPTS_FILE):
        os.makedirs(DATA_DIR, exist_ok=True)
        templates = _default_templates()
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_all(templates: list[dict]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


# ---- 默认模板 ----

def _default_templates() -> list[dict]:
    now = time.time()
    return [
        {
            "id": "traffic-light",
            "name": "十字路口交通灯",
            "category": "顺序控制",
            "description": "生成十字路口交通灯控制程序（SCL）",
            "content": (
                "你是一名西门子PLC工程师，使用TIA Portal V18编程。\n"
                "请生成一个十字路口交通灯控制程序。\n\n"
                "要求：\n"
                "- 使用SCL语言\n"
                "- 包含红灯、黄灯、绿灯控制\n"
                "- 东西方向和南北方向交替通行\n"
                "- 绿灯持续时间：{green_time}秒\n"
                "- 黄灯持续时间：{yellow_time}秒\n"
                "- 包含急停输入\n"
                "- 包含启动/停止按钮\n\n"
                "请生成完整的FB块，包含变量声明和逻辑代码。"
            ),
            "variables": [
                {"name": "green_time", "label": "绿灯时间(秒)", "default": "30", "type": "int"},
                {"name": "yellow_time", "label": "黄灯时间(秒)", "default": "3", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "motor-fwd-rev",
            "name": "电机正反转控制",
            "category": "运动控制",
            "description": "生成电机正反转控制FB（SCL/LAD）",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成一个电机正反转控制程序。\n\n"
                "要求：\n"
                "- 使用{language}语言\n"
                "- 包含正转启动、反转启动、停止按钮\n"
                "- 正反转互锁\n"
                "- 过载保护输入\n"
                "- 急停输入\n"
                "- 输出：正转接触器、反转接触器、故障指示\n"
                "- 带故障复位功能\n\n"
                "请生成完整的FB块。"
            ),
            "variables": [
                {"name": "language", "label": "编程语言", "default": "SCL", "type": "string"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "pid-controller",
            "name": "PID 温度调节",
            "category": "过程控制",
            "description": "生成PID温度控制程序（SCL）",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成一个PID温度控制程序。\n\n"
                "要求：\n"
                "- 使用SCL语言\n"
                "- 目标温度：{target_temp}°C\n"
                "- 采样周期：{sample_time}ms\n"
                "- 包含手动/自动切换\n"
                "- 输出限幅：0-100%\n"
                "- 包含加热器输出和冷却输出\n"
                "- PID参数可通过HMI调节\n\n"
                "请生成完整的FB块和DB。"
            ),
            "variables": [
                {"name": "target_temp", "label": "目标温度(°C)", "default": "100", "type": "int"},
                {"name": "sample_time", "label": "采样周期(ms)", "default": "500", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "modbus-rtu",
            "name": "Modbus RTU 通信",
            "category": "通信",
            "description": "生成Modbus RTU主站通信程序",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成Modbus RTU通信程序。\n\n"
                "要求：\n"
                "- 使用TIA Portal V18\n"
                "- 使用Modbus_Comm_Load和Modbus_Master功能块\n"
                "- 波特率：{baud_rate}\n"
                "- 数据格式：8数据位，{parity}校验，1停止位\n"
                "- 从站地址：{slave_address}\n"
                "- 读取保持寄存器和输入寄存器\n"
                "- 错误处理和通信超时\n\n"
                "请生成主站通信程序，包含数据映射和错误处理。"
            ),
            "variables": [
                {"name": "baud_rate", "label": "波特率", "default": "9600", "type": "string"},
                {"name": "parity", "label": "校验方式", "default": "无", "type": "string"},
                {"name": "slave_address", "label": "从站地址", "default": "1", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "step-sequence",
            "name": "步进顺控程序",
            "category": "顺序控制",
            "description": "生成步进顺控程序（SCL）",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成一个步进顺控程序。\n\n"
                "要求：\n"
                "- 使用SCL语言\n"
                "- 包含{step_count}个工步\n"
                "- 每步包含：启动条件、执行动作、完成条件\n"
                "- 包含手动/自动切换\n"
                "- 包含单步运行/连续运行模式\n"
                "- 包含急停和复位功能\n"
                "- 每一步都有超时保护和报警\n\n"
                "请生成完整的FB块。"
            ),
            "variables": [
                {"name": "step_count", "label": "工步数", "default": "4", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "analog-processing",
            "name": "模拟量信号处理",
            "category": "信号处理",
            "description": "生成模拟量采集和标定程序",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成模拟量信号处理程序。\n\n"
                "要求：\n"
                "- 使用SCL语言\n"
                "- 输入信号：{signal_type}（4-20mA / 0-10V）\n"
                "- 量程转换：{range_min}-{range_max}\n"
                "- 包含滤波处理\n"
                "- 包含断线检测\n"
                "- 包含上下限报警\n"
                "- 采样周期可配置\n\n"
                "请生成完整的FC块。"
            ),
            "variables": [
                {"name": "signal_type", "label": "信号类型", "default": "4-20mA", "type": "string"},
                {"name": "range_min", "label": "量程下限", "default": "0", "type": "int"},
                {"name": "range_max", "label": "量程上限", "default": "100", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "alarm-management",
            "name": "报警管理系统",
            "category": "系统功能",
            "description": "生成报警管理FC",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请生成一个报警管理程序。\n\n"
                "要求：\n"
                "- 使用SCL语言\n"
                "- 支持{alarm_count}个报警点\n"
                "- 每个报警包含：触发位、确认位、报警文本\n"
                "- 报警分级（警告/报警/紧急）\n"
                "- 首次报警记录\n"
                "- 报警时间戳\n"
                "- 蜂鸣器输出\n"
                "- 报警自动复位功能\n\n"
                "请生成完整的FC和DB。"
            ),
            "variables": [
                {"name": "alarm_count", "label": "报警数量", "default": "16", "type": "int"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "explain-code",
            "name": "解释PLC代码",
            "category": "辅助工具",
            "description": "让AI解释一段PLC代码的逻辑",
            "content": (
                "请解释下面的PLC代码：\n\n"
                "{code}\n\n"
                "请说明：\n"
                "1. 这段代码的功能是什么\n"
                "2. 关键变量的作用\n"
                "3. 逻辑执行流程\n"
                "4. 可能的优化建议"
            ),
            "variables": [
                {"name": "code", "label": "PLC代码", "default": "", "type": "string"},
            ],
            "created_at": now, "updated_at": now,
        },
        {
            "id": "generate-io-table",
            "name": "生成IO表",
            "category": "辅助工具",
            "description": "根据设备描述生成PLC IO表",
            "content": (
                "你是一名西门子PLC工程师。\n"
                "请根据以下设备描述生成PLC IO表：\n\n"
                "{description}\n\n"
                "请以表格形式列出：\n"
                "| 地址 | 符号名 | 数据类型 | 说明 | 设备位置 |\n"
                "|------|--------|----------|------|----------|\n\n"
                "包含：\n"
                "- 数字量输入\n"
                "- 数字量输出\n"
                "- 模拟量输入\n"
                "- 模拟量输出"
            ),
            "variables": [
                {"name": "description", "label": "设备描述", "default": "", "type": "string"},
            ],
            "created_at": now, "updated_at": now,
        },
    ]


# ---- API 路由 ----

@router.get("")
async def list_templates(category: str = ""):
    """获取所有Prompt模板，可按分类筛选"""
    templates = _load_all()
    if category:
        templates = [t for t in templates if t["category"] == category]
    return {"templates": templates, "total": len(templates)}


@router.get("/categories")
async def list_categories():
    """获取所有模板分类"""
    templates = _load_all()
    cats = {}
    for t in templates:
        c = t["category"]
        if c not in cats:
            cats[c] = 0
        cats[c] += 1
    return {"categories": [{"name": k, "count": v} for k, v in cats.items()]}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """获取单个模板详情（含完整内容）"""
    templates = _load_all()
    for t in templates:
        if t["id"] == template_id:
            return {"template": t}
    raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")


@router.post("", status_code=201)
async def create_template(data: TemplateCreate, _actor: str = Depends(require_local_session)):
    """创建新模板"""
    templates = _load_all()
    new_id = data.name.lower().replace(" ", "-").replace("_", "-")
    # 去重
    if any(t["id"] == new_id for t in templates):
        raise HTTPException(status_code=409, detail=f"模板 '{new_id}' 已存在")

    now = time.time()
    new_template = {
        "id": new_id,
        "name": data.name,
        "category": data.category,
        "description": data.description,
        "content": data.content,
        "variables": [v.model_dump() for v in data.variables],
        "created_at": now,
        "updated_at": now,
    }
    templates.append(new_template)
    _save_all(templates)
    return {"template": new_template}


@router.put("/{template_id}")
async def update_template(template_id: str, data: TemplateUpdate, _actor: str = Depends(require_local_session)):
    """更新模板"""
    templates = _load_all()
    for t in templates:
        if t["id"] == template_id:
            if data.name is not None:
                t["name"] = data.name
            if data.category is not None:
                t["category"] = data.category
            if data.description is not None:
                t["description"] = data.description
            if data.content is not None:
                t["content"] = data.content
            if data.variables is not None:
                t["variables"] = [v.model_dump() for v in data.variables]
            t["updated_at"] = time.time()
            _save_all(templates)
            return {"template": t}
    raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")


@router.delete("/{template_id}")
async def delete_template(template_id: str, _actor: str = Depends(require_local_session)):
    """删除模板"""
    templates = _load_all()
    for i, t in enumerate(templates):
        if t["id"] == template_id:
            templates.pop(i)
            _save_all(templates)
            return {"status": "deleted", "id": template_id}
    raise HTTPException(status_code=404, detail=f"模板 {template_id} 不存在")
