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

import ipaddress
import os
import re
from pathlib import Path, PureWindowsPath
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
        # 优先级：进程 os.environ 非空值 > .env 非空值 > 默认值。
        # 任一层的空值都不得压制另一层或 ${VAR:default} 的默认值，
        # 否则 .env 里的 "PLCSIM_TARGET_IP="（空值）会让 config.yaml
        # 的 ${PLCSIM_TARGET_IP:192.168.0.1} 解析为空串而非默认 IP。
        os_value = os.environ.get(var, "")
        if os_value != "":
            return os_value
        env_value = env.get(var, "")
        if env_value != "":
            return env_value
        return default

    return re.sub(r"\$\{([^}]+)\}", _replacer, value)


_PATH_KEYS = {
    "project_path", "install_dir", "output_dir",
    "dll_path", "templates_dir", "scl_templates_dir",
    "audit_log", "batch_log", "interlock_rules",
}

# 任意 scheme://（http/https/tcp/opc.tcp/mqtt/modbus+tcp…）都是网络端点，不是路径
_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")

# 点号分隔的主机名（如 plc.local、broker.mqtt.com）是网络标识，不是路径
_HOSTNAME_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$"
)

# 版本号（如 V2.30、1.2.3）是软件版本，不是路径
_VERSION_RE = re.compile(r"^[Vv]?\d+(?:\.\d+)+$")


def _looks_like_path(key: str, value: str) -> bool:
    """判断值是否像路径（需要 resolve 到绝对路径）"""
    # TIA 设备名可以包含 "/"，但它是工程对象身份，不是文件系统路径。
    if key == "device_name":
        return False
    # URL/URI 端点（任意 scheme://）不是路径
    if _URI_SCHEME_RE.match(value):
        return False
    # IP 地址（如 192.168.0.10）是网络标识，不是路径
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        return False
    # 显式声明路径意图的键始终 resolve
    if key in _PATH_KEYS:
        return True
    # 主机名（plc.local、broker.mqtt.com）与版本号（V2.30、1.2.3）不得被
    # 静默改写为绝对路径，否则 MODBUS_HOST 等非路径配置值会被损坏。
    if _HOSTNAME_RE.fullmatch(value) or _VERSION_RE.fullmatch(value):
        return False
    return bool(re.search(r"[\\/]|\.[a-z0-9]{2,6}$", value))


def _resolve_path(value: str, base_dir: Path = None) -> str:
    """将相对路径转为绝对路径"""
    # 控制目标路径是 Windows 语义（TIA 工程站、D:\… 盘符路径）。非 Windows
    # 平台上必须按 PureWindowsPath 识别，否则会被错误地拼到 base_dir 下。
    if PureWindowsPath(value).is_absolute():
        return value
    if base_dir is None:
        base_dir = _PROJECT_ROOT
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((base_dir / p).resolve())


class Config:
    """支持点号访问和 `${ENV}` 解析的配置对象"""

    def __init__(self, data: dict, env: dict = None, base_dir: Path = None):
        if not isinstance(data, dict):
            raise TypeError(
                f"配置数据必须是 dict，收到 {type(data).__name__}；"
                "请检查 YAML 文件顶层是否为映射"
            )
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_env", env or {})
        object.__setattr__(self, "_base", base_dir or _PROJECT_ROOT)
        object.__setattr__(self, "_cache", {})

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
                if key in self._cache:
                    return self._cache[key]
                val = _resolve_env(val, self._env)
                if _looks_like_path(key, val):
                    val = _resolve_path(val, self._base)
                self._cache[key] = val
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

    if not isinstance(raw, dict):
        raise ValueError(
            f"配置文件 {p} 顶层必须是 YAML 映射（dict），"
            f"实际得到: {'空文件或 null' if raw is None else type(raw).__name__}"
        )

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
