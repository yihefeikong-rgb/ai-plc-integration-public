"""AI PLC Assistant — 测试配置与共享 fixtures"""
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── 路径 ──────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.parent  # ai-plc-assistant/backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── 一次性导入真实 app ──────────────────────────────────────
# 必须在任何测试/清理之前导入，避免 pydantic 重新导入的兼容性问题
# 注意：app 中的全局单例（knowledge_engine 等）会在 import 时创建
# 它们使用相对路径，所以在 import 前要先 chdir
import os
_orig_cwd = os.getcwd()
os.chdir(str(BACKEND_DIR))
from main import app as _real_app
from routes import knowledge as _kb_routes
from routes import search as _search_routes
from routes import conversations as _conv_routes
from routes import projects as _proj_routes
os.chdir(str(_orig_cwd))


# ── 临时数据目录 ────────────────────────────────────────────
@pytest.fixture(scope="session")
def tmp_data_dir():
    """每个测试会话创建一次临时数据目录"""
    tmp = tempfile.mkdtemp(prefix="ai_plc_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


# ── Mock LLM 服务 ──────────────────────────────────────────
MOCK_LADDER_RESPONSE = """ASCII-LAD-V2

Variables:
I0.0    bStart     BOOL    启动按钮
I0.1    bStop      BOOL    停止按钮
Q0.0    qMotor     BOOL    电机输出

Network 1
Title: 启动保持

Comment:
按下启动按钮后自锁保持

|----[ bStart ]----[/ bStop ]----+----( qMotor )
|                                |
|----[ qMotor ]------------------+
"""

MOCK_STREAM_TOKENS = [
    {"token": "模拟", "type": "text"},
    {"token": "流式", "type": "text"},
    {"token": "输出", "type": "text"},
    {"token": "完成", "type": "done"},
]


@pytest.fixture(autouse=True)
def mock_llm():
    """
    全局 mock LLM 调用，避免真实 API 调用和计费。
    每个测试自动生效。
    注意：由于 workflow.py 中 from llm.service import chat 绑定了本地引用，
    需要 patch generator.workflow.chat 而非 llm.service.chat。
    """
    def _fake_stream(*args, **kwargs):
        for token in ["你", "好", "，", "这", "是", "测", "试", "。"]:
            yield token

    with patch("generator.workflow.chat") as mock_chat, \
         patch("llm.service.chat_with_fallback") as mock_fallback, \
         patch("llm.service.chat_stream") as mock_stream, \
         patch("routes.chat.chat_stream") as mock_chat_stream_routes, \
         patch("routes.chat.chat_with_fallback") as mock_chat_fallback_routes:

        mock_chat.return_value = MOCK_LADDER_RESPONSE
        mock_fallback.return_value = {
            "content": MOCK_LADDER_RESPONSE,
            "model": "deepseek",
            "fallback": False,
        }
        mock_stream.side_effect = _fake_stream
        mock_chat_stream_routes.side_effect = _fake_stream
        mock_chat_fallback_routes.return_value = {
            "content": MOCK_LADDER_RESPONSE,
            "model": "deepseek",
            "fallback": False,
        }
        yield


# ── FastAPI TestClient ─────────────────────────────────────
@pytest.fixture
def client():
    """创建 FastAPI TestClient (复用全局 app 实例)"""
    # 每次测试前清空测试相关表，保证测试隔离
    try:
        import main as _main_module
        if _main_module.project_store and _main_module.project_store._conn:
            _main_module.project_store._conn.execute("DELETE FROM projects")
            _main_module.project_store._conn.commit()
        if _main_module.conv_store and _main_module.conv_store._conn:
            _main_module.conv_store._conn.execute("DELETE FROM conversations")
            _main_module.conv_store._conn.execute("DELETE FROM messages")
            _main_module.conv_store._conn.commit()
    except Exception:
        pass

    with TestClient(_real_app) as c:
        yield c


# ── 测试用的 prompts.json ──────────────────────────────────
@pytest.fixture
def sample_prompts():
    """创建测试用 prompts.json 数据"""
    data = [
        {
            "id": "motor-control",
            "name": "电机控制",
            "category": "运动控制",
            "description": "电机启停控制",
            "content": "请生成电机控制程序，使用SCL语言。",
            "variables": [],
            "created_at": 1000.0,
            "updated_at": 1000.0,
        },
        {
            "id": "traffic-light",
            "name": "交通灯控制",
            "category": "顺序控制",
            "description": "十字路口交通灯",
            "content": "请生成交通灯控制程序。",
            "variables": [
                {"name": "green_time", "label": "绿灯时间", "default": "30", "type": "int"}
            ],
            "created_at": 1000.0,
            "updated_at": 1000.0,
        },
    ]

    prompts_dir = BACKEND_DIR / "data"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompts_file = prompts_dir / "prompts.json"

    # 备份原始文件
    original = None
    if prompts_file.exists():
        original = prompts_file.read_text(encoding="utf-8")

    prompts_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    yield data

    # 恢复
    if original:
        prompts_file.write_text(original, encoding="utf-8")
    elif prompts_file.exists():
        current = prompts_file.read_text(encoding="utf-8")
        if current == json.dumps(data, ensure_ascii=False, indent=2):
            prompts_file.unlink(missing_ok=True)


# ── 测试用文件 fixtures ──────────────────────────────────
@pytest.fixture
def sample_txt_file(tmp_path):
    """创建测试用 TXT 文件"""
    p = tmp_path / "plc_guide.txt"
    p.write_text(
        "西门子 S7-1200 PLC 编程指南\n"
        "本指南介绍 PROFINET 通信和基础指令。\n"
        "适用于 TIA Portal V21。\n",
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def sample_scl_file(tmp_path):
    """创建测试用 SCL 文件"""
    p = tmp_path / "MotorControl.scl"
    p.write_text(
        'FUNCTION_BLOCK "MotorControl"\n'
        "{S7_Optimized_Access := 'TRUE'}\n"
        "VERSION : 0.1\n"
        "   VAR_INPUT\n"
        "      bStart : Bool;\n"
        "      bStop : Bool;\n"
        "   END_VAR\n"
        "   VAR_OUTPUT\n"
        "      qMotor : Bool;\n"
        "   END_VAR\n"
        "BEGIN\n"
        "   // 电机启停控制\n"
        "END_FUNCTION_BLOCK\n",
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def sample_csv_file(tmp_path):
    """创建测试用 CSV 文件"""
    p = tmp_path / "io_table.csv"
    p.write_text(
        "Name,Address,DataType,Comment\n"
        "bStart,I0.0,Bool,启动按钮\n"
        "bStop,I0.1,Bool,停止按钮\n"
        "qMotor,Q0.0,Bool,电机输出\n",
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture
def sample_xml_file(tmp_path):
    """创建测试用 XML 文件（PLCopen XML 格式）"""
    p = tmp_path / "TestBlock.xml"
    p.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<SW.Blocks.FB ID="0" Name="TestBlock">\n'
        '  <AttributeList>\n'
        '    <Name>TestBlock</Name>\n'
        '    <BlockType>FB</BlockType>\n'
        '    <Title>测试功能块</Title>\n'
        '  </AttributeList>\n'
        '  <ObjectList>\n'
        '    <SW.Blocks.CompileUnit ID="1" Name="CompileUnit1">\n'
        '      <PlcBlockLocalMember Name="bStart" DataType="Bool"/>\n'
        '    </SW.Blocks.CompileUnit>\n'
        '  </ObjectList>\n'
        '</SW.Blocks.FB>\n',
        encoding="utf-8",
    )
    return str(p)
