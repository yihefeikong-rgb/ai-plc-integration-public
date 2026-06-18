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
MOCK_LADDER_RESPONSE = """# 电机启动/停止控制

> 带自锁的电机启停控制电路

## 变量表
| 地址 | 符号 | 类型 | 注释 |
|------|------|------|------|
| I0.0 | bStart | Bool | 启动按钮 |
| I0.1 | bStop | Bool | 停止按钮 |
| Q0.0 | qMotor | Bool | 电机输出 |

## Network 1: 启动保持
// 按下启动按钮后自锁保持
```
     bStart         bStop         qMotor
------| |----+-------|/|----------( )--
             |
             | qMotor
             +---| |
```"""

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
    with patch("generator.workflow.chat") as mock_chat, \
         patch("llm.service.chat_with_fallback") as mock_fallback:

        mock_chat.return_value = MOCK_LADDER_RESPONSE
        mock_fallback.return_value = MOCK_LADDER_RESPONSE

        yield


# ── FastAPI TestClient ─────────────────────────────────────
@pytest.fixture
def client():
    """创建 FastAPI TestClient (复用全局 app 实例)"""
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
