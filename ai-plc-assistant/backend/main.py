"""AI PLC Assistant — FastAPI 后端服务"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings as app_config
from routes import chat, models, knowledge, search, prompts, generate, conversations, projects
from routes import settings as settings_route
from knowledge.engine import KnowledgeEngine
from search.indexer import SearchIndex
from storage.conversations import ConversationStore
from storage.projects import ProjectStore
from storage.app_settings import AppSettings, set_settings_store

# 知识库引擎（全局单例）
knowledge_engine = KnowledgeEngine(db_path=app_config.vector_db_path)

# PLC 搜索引擎（全局单例）
search_engine = SearchIndex(db_path=app_config.project_search_db)

# 对话存储（全局单例）
conv_store = ConversationStore(db_path=app_config.conversations_db)

# 项目存储（全局单例）
project_store = ProjectStore(db_path=app_config.conversations_db.replace("conversations", "projects"))

# 应用设置（全局单例）
app_settings_store = AppSettings(file_path="data/settings.json")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化所有引擎"""
    knowledge_engine.initialize()
    knowledge.set_engine(knowledge_engine)
    search_engine.initialize()
    search.set_engine(search_engine)
    conv_store.initialize()
    conversations.set_store(conv_store)
    project_store.initialize()
    projects.set_store(project_store)
    app_settings_store.initialize()
    set_settings_store(app_settings_store)
    yield


app = FastAPI(
    title="AI PLC Assistant API",
    version="0.1.0",
    description="工业自动化 AI 工作台后端服务",
    lifespan=lifespan,
)

# CORS — 允许 Electron 前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000", "null"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_origin_regex=".*",
)

# 注册路由
app.include_router(models.router, prefix="/api/models", tags=["模型管理"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI 对话"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(search.router, prefix="/api/search", tags=["工程搜索"])
app.include_router(prompts.router, prefix="/api/prompts", tags=["Prompt 模板"])
app.include_router(generate.router, prefix="/api/generate", tags=["梯形图生成"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["对话历史"])
app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
app.include_router(settings_route.router, prefix="/api/settings", tags=["设置"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=app_config.host, port=app_config.port, reload=True)
