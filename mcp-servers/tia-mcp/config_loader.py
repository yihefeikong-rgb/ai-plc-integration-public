"""
统一配置加载器 — 所有脚本从此获取配置，消灭硬编码路径。

用法:
    from config_loader import cfg

    project = cfg.tia.project_path    # 点号访问
    dll     = cfg.cartgen.dll_path    # 自动转绝对路径
    api_key = cfg.deepseek.api_key    # 自动解析 ${ENV}

环境变量覆盖:
    config.yaml 中的 ${VAR:默认值} 语法自动解析，
    优先读 .env 文件，其次读系统环境变量。
"""
import os
import re
import yaml
import sys
from pathlib import Path
from typing import Any


# ═══ Windows 控制台编码修复 ═══
# 在 GBK 编码的控制台中，emoji 等 Unicode 字符会导致 UnicodeEncodeError。
# 如果 stdout 不是 UTF-8，切换到 UTF-8 并启用 errors='replace' 降级。
if hasattr(sys.stdout, 'reconfigure') and sys.stdout.encoding:
    enc = sys.stdout.encoding.lower()
    if 'utf' not in enc and 'utf8' not in enc:
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


# ═══ 项目根目录 ═══
_PROJECT_ROOT = Path(__file__).parent.parent.parent  # 上三级


def _load_env_file() -> dict:
    """读取项目根目录 .env 文件（兼容旧版）"""
    env = {}
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
    return re.sub(r'\$\{([^}]+)\}', _replacer, value)


def _resolve_path(value: str) -> str:
    """将相对路径转为绝对路径（相对于项目根目录）"""
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((_PROJECT_ROOT / p).resolve())


class _ConfigNode:
    """支持点号访问的配置节点（递归）"""

    def __init__(self, data: dict, root: "_Config"):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_root", root)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        data = self._data
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                return _ConfigNode(val, self._root)
            if isinstance(val, list):
                return val
            # 字符串：解析环境变量 + 如果是路径则 resolve
            if isinstance(val, str):
                val = _resolve_env(val, self._root._env)
                # 对以路径特征结尾的值做 resolve
                if _looks_like_path(key, val):
                    val = _resolve_path(val)
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


class _Config:
    """顶层配置对象"""

    def __init__(self, data: dict):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_env", _load_env_file())

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        data = self._data
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                return _ConfigNode(val, self)
            return val
        raise AttributeError(f"配置节不存在: {key}")

    def __getitem__(self, key: str) -> Any:
        return self.__getattr__(key)

    def __repr__(self):
        return f"<Config: {list(self._data.keys())}>"


def _looks_like_path(key: str, value: str) -> bool:
    """判断值是否像路径（需要 resolve）"""
    # URL 不是路径
    if value.startswith(("http://", "https://", "tcp://")):
        return False
    path_keys = {
        "project_path", "install_dir", "output_dir",
        "dll_path", "templates_dir", "scl_templates_dir",
        "audit_log", "batch_log", "interlock_rules",
    }
    if key in path_keys:
        return True
    # 也检查是否包含路径分隔符或文件扩展名
    return bool(re.search(r'[\\/]|\.[a-z0-9]{2,6}$', value))


# ═══ LadderSpec JSON Schema 校验 ═══

_SCHEMA_PATH = Path(__file__).parent / "ladder_spec.schema.json"
_SCHEMA_CACHE = None


def _get_schema():
    """加载 JSON Schema（惰性 + 缓存）"""
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        import json
        with open(_SCHEMA_PATH, encoding="utf-8") as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def validate_ladder_spec(spec: dict) -> dict:
    """校验 LadderSpec JSON，返回 {"valid": True} 或 {"valid": False, "errors": [...]}

    在 DeepSeek 输出后、CartGen 调用前使用，避免 CartGen 因格式错误崩溃。
    """
    import json as _json
    try:
        import jsonschema
    except ImportError:
        # jsonschema 未安装时，做基本检查
        errors = _basic_validate(spec)
        if errors:
            return {"valid": False, "errors": errors, "warning": "jsonschema 未安装，仅做基本检查"}
        return {"valid": True}

    schema = _get_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors = []
    for err in validator.iter_errors(spec):
        path = " → ".join(str(p) for p in err.absolute_path) or "(根)"
        errors.append(f"{path}: {err.message}")

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True}


def _basic_validate(spec: dict) -> list:
    """无 jsonschema 库时的基本检查"""
    errors = []

    if not isinstance(spec, dict):
        return ["根: 不是 JSON 对象"]

    # 必填字段
    for field in ["blockName", "blockNumber", "interface", "networks"]:
        if field not in spec:
            errors.append(f"根: 缺少必填字段 '{field}'")

    if not isinstance(spec.get("networks"), list) or len(spec.get("networks", [])) == 0:
        errors.append("networks: 必须是非空数组")

    # 元素类型检查
    valid_types = {"normally_open", "normally_closed", "coil", "coil_set", "coil_reset", "timer_on_delay", "timer_off_delay"}
    for i, net in enumerate(spec.get("networks", [])):
        if not isinstance(net, dict):
            errors.append(f"networks[{i}]: 不是对象")
            continue
        if "elements" not in net:
            errors.append(f"networks[{i}]: 缺少 elements")
            continue
        for j, el in enumerate(net.get("elements", [])):
            if not isinstance(el, dict):
                errors.append(f"networks[{i}].elements[{j}]: 不是对象")
                continue
            if "type" not in el:
                errors.append(f"networks[{i}].elements[{j}]: 缺少 type")
            elif el["type"] not in valid_types:
                errors.append(
                    f"networks[{i}].elements[{j}].type: '{el['type']}' "
                    f"不是有效类型，允许: {', '.join(sorted(valid_types))}"
                )
            if "operand" not in el:
                errors.append(f"networks[{i}].elements[{j}]: 缺少 operand")

    return errors


# ═══ LadderSpec 安全校验 ═══

def safety_validate_ladder(spec: dict) -> dict:
    """校验 LadderSpec 是否满足安全规则。

    检查:
      - 所有输出是否串联了急停互锁（normally_closed iStop）
      - 正反转是否有互锁（正转网络含 normally_closed oRunRev）
      - 过载保护是否串联 normally_closed iOverload

    Returns:
        {"safe": True} 或 {"safe": False, "warnings": [...]}
    """
    warnings = []

    if not isinstance(spec, dict):
        return {"safe": False, "warnings": ["输入不是 JSON 对象"]}

    networks = spec.get("networks", [])
    if not networks:
        return {"safe": False, "warnings": ["没有网络"]}

    # 收集所有输出变量名
    output_names = set()
    for out in spec.get("interface", {}).get("outputs", []):
        output_names.add(out.get("name", ""))

    # 收集所有输入变量名
    input_names = set()
    for inp in spec.get("interface", {}).get("inputs", []):
        input_names.add(inp.get("name", ""))

    # 检查是否有急停输入
    has_estop_input = any("stop" in n.lower() or "emergency" in n.lower() for n in input_names)
    has_overload_input = any("overload" in n.lower() or "fault" in n.lower() for n in input_names)

    # 检查是否有线圈输出
    has_motor_outputs = any(
        n.startswith("o") and ("fwd" in n.lower() or "rev" in n.lower() or "run" in n.lower())
        for n in output_names
    )

    # 逐网络检查
    has_estop_network = False
    has_fwd_rev_interlock = False

    for i, net in enumerate(networks):
        elements = net.get("elements", [])
        for el in elements:
            op = (el.get("operand") or "").lower()
            typ = el.get("type", "")

            # 检查急停常闭触点
            if typ == "normally_closed" and ("stop" in op or "emergency" in op):
                has_estop_network = True

            # 检查正反转互锁（正转网络中的 normally_closed oRunRev 或反转网络中的 normally_closed oRunFwd）
            if typ == "normally_closed" and (("runrev" in op or "runfwd" in op) or
                                              ("rev" in op and "fwd" not in op and has_motor_outputs) or
                                              ("fwd" in op and "rev" not in op and has_motor_outputs)):
                has_fwd_rev_interlock = True

    if has_motor_outputs and not has_estop_network:
        warnings.append("有电机类输出，但未检测到急停互锁（串联 normally_closed iStop）")

    if has_motor_outputs and not has_fwd_rev_interlock:
        warnings.append("有正反转输出，但未检测到正反转互锁（正转网络应含 normally_closed oRunRev）")

    if has_motor_outputs and not has_overload_input:
        warnings.append("有电机类输出，但未检测到过载保护输入变量（建议命名含 Overload）")

    if warnings:
        return {"safe": False, "warnings": warnings}
    return {"safe": True}


# ═══ 加载配置 ═══
_config_path = Path(__file__).parent / "config.yaml"
with open(_config_path, encoding="utf-8") as f:
    _raw = yaml.safe_load(f)

cfg = _Config(_raw)
