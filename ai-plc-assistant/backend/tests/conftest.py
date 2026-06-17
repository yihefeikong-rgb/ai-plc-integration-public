"""测试基础设施 — fixtures, mock, 临时数据库"""

import os
import sys
import json
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# 确保 backend 目录在 sys.path 中
BACKEND_DIR = str(Path(__file__).parent.parent)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tests.mock_llm import mock_chat, mock_chat_with_fallback, mock_chat_stream


# ---- 临时目录 fixture ----

@pytest.fixture
def tmp_data_dir(tmp_path):
    """创建临时数据目录结构"""
    (tmp_path / "vector_db").mkdir()
    (tmp_path / "knowledge").mkdir()
    return tmp_path


# ---- Mock LLM fixtures ----

@pytest.fixture(autouse=True)
def patch_llm(monkeypatch):
    """全局 mock LLM — 所有测试自动生效, 禁止真实 API 调用"""
    monkeypatch.setattr("llm.service.chat", mock_chat)
    monkeypatch.setattr("llm.service.chat_with_fallback", mock_chat_with_fallback)
    monkeypatch.setattr("llm.service.chat_stream", mock_chat_stream)


# ---- TestClient fixture ----

@pytest.fixture
def test_app(tmp_data_dir):
    """创建使用临时数据库的 FastAPI 测试应用"""
    # 创建临时设置文件
    settings_path = str(tmp_data_dir / "settings.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump({
            "deepseek_api_key": "test-key-mock",
            "deepseek_base_url": "https://api.deepseek.com",
            "deepseek_model": "deepseek-v4-flash",
        }, f)

    from knowledge.engine import KnowledgeEngine
    from search.indexer import SearchIndex
    from storage.conversations import ConversationStore
    from storage.projects import ProjectStore
    from storage.app_settings import AppSettings, set_settings_store
    from routes import chat, models, knowledge, search, prompts, generate, conversations, projects
    from routes import settings as settings_route

    # 初始化临时引擎
    ke = KnowledgeEngine(db_path=str(tmp_data_dir / "vector_db"))
    se = SearchIndex(db_path=str(tmp_data_dir / "search.db"))
    cs = ConversationStore(db_path=str(tmp_data_dir / "conversations.db"))
    ps = ProjectStore(db_path=str(tmp_data_dir / "projects.db"))
    app_settings = AppSettings(file_path=settings_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        ke.initialize()
        knowledge.set_engine(ke)
        se.initialize()
        search.set_engine(se)
        cs.initialize()
        conversations.set_store(cs)
        ps.initialize()
        projects.set_store(ps)
        app_settings.initialize()
        set_settings_store(app_settings)
        yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(models.router, prefix="/api/models")
    app.include_router(chat.router, prefix="/api/chat")
    app.include_router(knowledge.router, prefix="/api/knowledge")
    app.include_router(search.router, prefix="/api/search")
    app.include_router(prompts.router, prefix="/api/prompts")
    app.include_router(generate.router, prefix="/api/generate")
    app.include_router(conversations.router, prefix="/api/conversations")
    app.include_router(projects.router, prefix="/api/projects")
    app.include_router(settings_route.router, prefix="/api/settings")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "test"}

    return app


@pytest.fixture
def client(test_app):
    """FastAPI TestClient — 自动触发 lifespan"""
    with TestClient(test_app) as c:
        yield c


# ---- 测试样本 fixtures ----

@pytest.fixture
def sample_scl_file(tmp_path):
    """创建一个小型 SCL 样本文件"""
    content = '''FUNCTION_BLOCK "MotorControl"
TITLE = '电机控制'
VERSION : 0.1

VAR_INPUT
    bStart : Bool;   // 启动按钮
    bStop : Bool;    // 停止按钮
END_VAR

VAR_OUTPUT
    qMotor : Bool;   // 电机输出
END_VAR

BEGIN
    qMotor := bStart AND NOT bStop;
END_FUNCTION_BLOCK
'''
    p = tmp_path / "MotorControl.scl"
    p.write_text(content, encoding="utf-8")
    return str(p)


@pytest.fixture
def sample_csv_file(tmp_path):
    """创建一个小型 CSV IO 表样本"""
    content = """Name,Address,DataType,Comment
bStart,I0.0,Bool,启动按钮
bStop,I0.1,Bool,停止按钮
qMotor,Q0.0,Bool,电机输出
"""
    p = tmp_path / "io_table.csv"
    p.write_text(content, encoding="utf-8")
    return str(p)


@pytest.fixture
def sample_xml_file(tmp_path):
    """创建一个小型 PLC 块 XML 样本"""
    content = '''<?xml version="1.0" encoding="utf-8"?>
<PlcBlock>
  <AttributeList>
    <Name>TestBlock</Name>
    <BlockType>FB</BlockType>
    <Title>Test Function Block</Title>
  </AttributeList>
  <Member>
    <AttributeList>
      <Name>bInput</Name>
      <DataType>Bool</DataType>
      <Comment>输入信号</Comment>
      <SectionType>Input</SectionType>
    </AttributeList>
  </Member>
</PlcBlock>
'''
    p = tmp_path / "TestBlock.xml"
    p.write_text(content, encoding="utf-8")
    return str(p)


@pytest.fixture
def sample_txt_file(tmp_path):
    """创建一个小型 TXT 知识库文件"""
    content = """西门子 S7-1200 PLC 编程指南

第一章：基础知识
PLC 是可编程逻辑控制器的缩写。
S7-1200 支持 SCL、LAD、FBD 三种编程语言。

第二章：通信配置
支持 PROFINET、Modbus TCP/RTU 等通信协议。
PUT/GET 通信需要在硬件配置中启用。
"""
    p = tmp_path / "plc_guide.txt"
    p.write_text(content, encoding="utf-8")
    return str(p)
