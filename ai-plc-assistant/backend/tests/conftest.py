"""AI PLC Assistant — 测试配置与共享 fixtures。"""
import json
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

# ── 路径 ──────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).parent.parent  # ai-plc-assistant/backend
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# ── 测试进程级隔离 ──────────────────────────────────────────
# 必须在导入 main 前设置。main 会创建全局存储单例；若先导入，测试清理
# 可能碰到开发者的 data/ 目录或真实凭据。
_TEST_DATA_ROOT = Path(tempfile.mkdtemp(prefix="ai_plc_test_"))
_TEST_PROJECT_DIR = _TEST_DATA_ROOT / "projects"
_TEST_PROJECT_DIR.mkdir(parents=True, exist_ok=True)
os.environ.update({
    "AI_PLC_OFFLINE_TESTING": "1",
    "VECTOR_DB_PATH": str(_TEST_DATA_ROOT / "vector_db"),
    "CONVERSATIONS_DB": str(_TEST_DATA_ROOT / "conversations.db"),
    "PROJECT_SEARCH_DB": str(_TEST_DATA_ROOT / "search_index.db"),
    "APP_SETTINGS_PATH": str(_TEST_DATA_ROOT / "settings.json"),
    "PROJECT_DIR": str(_TEST_PROJECT_DIR),
    "PROMPTS_FILE": str(_TEST_DATA_ROOT / "prompts.json"),
    "AI_PLC_LOG_DIR": str(_TEST_DATA_ROOT / "logs"),
    "AI_PLC_MCP_OWNER_LOCK": str(_TEST_DATA_ROOT / "mcp-owner.lock"),
    "EMBEDDING_MODEL": "offline-test",
    "LOCAL_API_TOKEN": "test-local-api-token",
    # 覆盖可能由开发环境 .env 提供的真实凭据，测试绝不迁移或读取它们。
    "OPENAI_API_KEY": "",
    "CLAUDE_API_KEY": "",
    "KIMI_API_KEY": "",
    "DEEPSEEK_API_KEY": "",
    "OPENROUTER_API_KEY": "",
    "CUSTOM_API_KEY": "",
})

# ── 一次性导入真实 app ──────────────────────────────────────
# app 的全局单例已全部被上方环境变量重定向到系统临时目录。
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
    """返回当前测试会话的隔离数据根目录。"""
    return _TEST_DATA_ROOT


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """测试结束后仅删除本进程创建的临时目录。"""
    yield
    import main as _main_module
    from chromadb.api.shared_system_client import SharedSystemClient

    for store in (_main_module.conv_store, _main_module.project_store):
        if store._conn is not None:
            store._conn.close()
            store._conn = None
    _main_module.search_engine.close()
    chroma_client = _main_module.knowledge_engine._client
    if chroma_client is not None:
        chroma_system = getattr(chroma_client, "_system", None)
        if chroma_system is not None:
            chroma_system.stop()
    _main_module.knowledge_engine._collection = None
    _main_module.knowledge_engine._client = None
    SharedSystemClient.clear_system_cache()
    logging.shutdown()
    shutil.rmtree(_TEST_DATA_ROOT)


@pytest.fixture(scope="session", autouse=True)
def isolate_keyring():
    """用进程内凭据库替身，测试不访问用户的系统凭据。"""
    credentials: dict[tuple[str, str], str] = {}

    def get_password(service: str, username: str) -> str | None:
        return credentials.get((service, username))

    def set_password(service: str, username: str, password: str) -> None:
        credentials[(service, username)] = password

    def delete_password(service: str, username: str) -> None:
        credentials.pop((service, username), None)

    with patch("storage.app_settings.keyring.get_password", side_effect=get_password), \
         patch("storage.app_settings.keyring.set_password", side_effect=set_password), \
         patch("storage.app_settings.keyring.delete_password", side_effect=delete_password):
        yield credentials


# ── Mock 编排层 bootstrap/shutdown ──────────────────────────
@pytest.fixture(scope="session", autouse=True)
def mock_orchestrator_lifespan():
    """全局 mock 编排层启动/关闭，避免测试时连接真实 MCP 服务器。"""
    mock_bootstrap = AsyncMock(return_value=None)
    mock_shutdown = AsyncMock(return_value=None)
    with patch("main.bootstrap", mock_bootstrap), \
         patch("main.orchestrator_shutdown", mock_shutdown):
        yield


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

    # 重置 generate 模块级限流状态，避免测试间累积触发 429
    try:
        from routes import generate as _gen_routes
        _gen_routes._generate_history.clear()
    except Exception:
        pass

    with TestClient(_real_app) as c:
        # SearchIndex 是进程级单例；每个用例从同一份隔离索引开始。
        try:
            import main as _main_module
            _main_module.search_engine.clear()
        except Exception:
            pass
        c.headers.update({"X-Local-Api-Token": os.environ["LOCAL_API_TOKEN"]})
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

    prompts_file = Path(os.environ["PROMPTS_FILE"])
    prompts_file.parent.mkdir(parents=True, exist_ok=True)
    prompts_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    yield data
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
