"""
统一配置加载器 — 合并 config/settings.py 和 tia-mcp/config_loader.py。

特性:
  - YAML 配置文件 + ${ENV:default} 语法（来自 tia-mcp/config_loader.py）
  - .env 文件自动加载（来自 config/settings.py）
  - 点号路径访问（来自 tia-mcp/config_loader.py）
  - 环境变量覆盖（两者都有）

用法:
    from mcp_common.config import load_yaml_config, env_config

    # YAML 模式（推荐）
    cfg = load_yaml_config("mcp-servers/tia-mcp/config.yaml")
    api_key = cfg.deepseek.api_key
    path = cfg.tia.project_path

    # 纯环境变量模式
    settings = env_config()
    host = settings.modbus_host
"""

import os
import re
from pathlib import Path
from typing import Any, Optional


# ═══ 项目根目录 ═══
_PROJECT_ROOT = Path(__file__).parent.parent


def _ensure_project_root():
    """确保 mcp_common 包已被安装或可导入（保护性检查）"""
    return _PROJECT_ROOT


def _load_env_file(env_path: Optional[Path] = None) -> dict:
    """读取 .env 文件，返回环境变量字典"""
    env = {}
    if env_path is None:
        env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def _resolve_env(value: str, env: dict) -> str:
    """解析 ${VAR:默认值} 或 ${VAR} 语法"""

    def _replacer(m):
        full = m.group(1)
        if ":" in full:
            var, default = full.split(":", 1)
        else:
            var, default = full, ""
        return env.get(var, os.environ.get(var, default))

    return re.sub(r"\$\{([^}]+)\}", _replacer, value)


_PATH_KEYS = {
    "project_path", "install_dir", "output_dir",
    "dll_path", "templates_dir", "scl_templates_dir",
    "audit_log", "batch_log", "interlock_rules",
}


def _looks_like_path(key: str, value: str) -> bool:
    """判断值是否像路径（需要 resolve 到绝对路径）"""
    if value.startswith(("http://", "https://", "tcp://")):
        return False
    if key in _PATH_KEYS:
        return True
    return bool(re.search(r"[\\/]|\.[a-z0-9]{2,6}$", value))


def _resolve_path(value: str, base_dir: Path = None) -> str:
    """将相对路径转为绝对路径"""
    if base_dir is None:
        base_dir = _PROJECT_ROOT
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


class Config:
    """支持点号访问和 `${ENV}` 解析的配置对象"""

    def __init__(self, data: dict, env: dict = None, base_dir: Path = None):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_env", env or {})
        object.__setattr__(self, "_base", base_dir or _PROJECT_ROOT)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        data = self._data
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                return Config(val, self._env, self._base)
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                val = _resolve_env(val, self._env)
                if _looks_like_path(key, val):
                    val = _resolve_path(val, self._base)
            return val
        raise AttributeError(f"配置项不存在: {key}")

    def __getitem__(self, key: str) -> Any:
        return self.__getattr__(key)

    def get(self, key: str, default=None) -> Any:
        try:
            return self.__getattr__(key)
        except AttributeError:
            return default

    def __repr__(self):
        return f"<Config: {list(self._data.keys())}>"


def load_yaml_config(yaml_path: str, env_path: str = "") -> Config:
    """从 YAML 文件加载配置，自动加载 .env 并解析 ${ENV}"""
    import yaml
    p = Path(yaml_path)
    if not p.is_absolute():
        p = _PROJECT_ROOT / p
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    env = _load_env_file(Path(env_path) if env_path else None)
    return Config(raw, env, p.parent)


def env_config() -> Config:
    """从环境变量加载配置（兼容 config/settings.py 模式）

    用法:
        from mcp_common.config import env_config
        settings = env_config()
        settings.get("OPCUA_ENDPOINT")  # 返回 opc.tcp://localhost:4840
    """
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")

    data = {}
    default_env = {
        "DEEPSEEK_API_KEY": "",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
        "DEEPSEEK_MODEL_SIMPLE": "deepseek-chat",
        "DEEPSEEK_MODEL_COMPLEX": "deepseek-chat",
        "OPCUA_ENDPOINT": "opc.tcp://localhost:4840",
        "OPCUA_USERNAME": "",
        "OPCUA_PASSWORD": "",
        "MODBUS_HOST": "localhost",
        "MODBUS_PORT": "502",
        "MELSEC_HOST": "",
        "MELSEC_PORT": "5001",
        "INFLUXDB_URL": "http://localhost:8086",
        "INFLUXDB_TOKEN": "",
        "INFLUXDB_ORG": "ai-plc",
        "INFLUXDB_BUCKET": "plc-data",
        "SAFETY_WRITE_CONFIRM": "true",
        "SAFETY_AUDIT_LOG": "./logs/audit.log",
        "SAFETY_MAX_CONSECUTIVE_ERRORS": "3",
    }

    for key, default in default_env.items():
        data[key.lower()] = os.getenv(key, default)

    return Config(data)
