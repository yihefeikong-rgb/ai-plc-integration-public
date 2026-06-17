"""AI PLC Assistant 配置"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 服务配置
    host: str = "127.0.0.1"
    port: int = 8000

    # 模型 API 配置
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"

    claude_api_key: str = ""
    claude_base_url: str = "https://api.anthropic.com/v1"
    claude_model: str = "claude-sonnet-4-20250514"

    kimi_api_key: str = ""
    kimi_base_url: str = "https://api.moonshot.cn/v1"
    kimi_model: str = "moonshot-v1-8k"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-sonnet-4"

    # 知识库配置
    knowledge_dir: str = "data/knowledge"
    vector_db_path: str = "data/vector_db"

    # 对话存储
    conversations_db: str = "data/conversations.db"

    # PLC 工程搜索配置
    project_dir: str = ""                     # 默认项目目录（空 = 仅在手动索引时指定）
    project_search_db: str = "data/search_index.db"  # FTS5 索引数据库路径

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
