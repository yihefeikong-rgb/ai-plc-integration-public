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
import ipaddress
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
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
_TARGET_ALIASES = {
    ("tia", "version"): "tia_version",
    ("tia", "project_path"): "project_path",
    ("simulation", "advanced", "plc_ip"): "plc_ip",
    ("factory_io", "plcsim_instance"): "plcsim_instance",
    ("factory_io", "tcpip", "host"): "plc_ip",
}
_MISSING = object()


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
        resolved = env.get(var)
        if not isinstance(resolved, str) or not resolved.strip():
            resolved = os.environ.get(var)
        if not isinstance(resolved, str) or not resolved.strip():
            resolved = default
        return resolved
    return re.sub(r'\$\{([^}]+)\}', _replacer, value)


def _resolve_path(value: str) -> str:
    """将相对路径转为绝对路径（相对于项目根目录）。

    控制目标路径是 Windows 语义（TIA 工程站）；在非 Windows 平台上
    运行时，Windows 绝对路径必须按 PureWindowsPath 识别，否则会被
    错误地拼接到项目根目录下。
    """
    if PureWindowsPath(value).is_absolute():
        return value
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((_PROJECT_ROOT / p).resolve())


class _ConfigNode:
    """支持点号访问的配置节点（递归）"""

    def __init__(self, data: dict, root: "_Config", path: tuple[str, ...] = ()):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_root", root)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, key: str) -> Any:
        if key.startswith("_"):
            return object.__getattribute__(self, key)
        data = self._data
        if key in data:
            val = data[key]
            if isinstance(val, dict):
                return _ConfigNode(val, self._root, self._path + (key,))
            if isinstance(val, list):
                return val
            # 字符串：解析环境变量 + 如果是路径则 resolve
            if isinstance(val, str):
                val = _resolve_env(val, self._root._env)
                # 对以路径特征结尾的值做 resolve
                if _looks_like_path(key, val):
                    val = _resolve_path(val)
            return val
        alias = self._root._target_alias(self._path + (key,))
        if alias is not _MISSING:
            return alias
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
                return _ConfigNode(val, self, (key,))
            return val
        raise AttributeError(f"配置节不存在: {key}")

    def _target_alias(self, path: tuple[str, ...]) -> Any:
        target_key = _TARGET_ALIASES.get(path)
        if target_key is None:
            return _MISSING
        target = self._data.get("target")
        if not isinstance(target, dict) or target_key not in target:
            raise AttributeError(f"唯一控制目标缺少配置项: target.{target_key}")
        value = target[target_key]
        if isinstance(value, str):
            value = _resolve_env(value, self._env)
            if _looks_like_path(target_key, value):
                value = _resolve_path(value)
        return value

    def __getitem__(self, key: str) -> Any:
        return self.__getattr__(key)

    def __repr__(self):
        return f"<Config: {list(self._data.keys())}>"


def _looks_like_path(key: str, value: str) -> bool:
    """判断值是否像路径（需要 resolve）"""
    # URL 不是路径
    if value.startswith(("http://", "https://", "tcp://")):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
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
    supported_types = {"Bool", "Int", "Real", "Word"}
    timer_types = {"timer_on_delay", "timer_off_delay"}
    time_pattern = re.compile(r"^(?:T#|TIME#)(?:\d+(?:MS|US|NS|D|H|M|S))+$")

    if not isinstance(spec, dict):
        return ["根: 不是 JSON 对象"]

    # 必填字段
    for field in ["blockName", "blockNumber", "interface", "networks"]:
        if field not in spec:
            errors.append(f"根: 缺少必填字段 '{field}'")

    if not isinstance(spec.get("networks"), list) or len(spec.get("networks", [])) == 0:
        errors.append("networks: 必须是非空数组")

    interface = spec.get("interface", {})
    if not isinstance(interface, dict):
        errors.append("interface: 必须是对象")
    else:
        for section in ("inputs", "outputs"):
            variables = interface.get(section)
            if not isinstance(variables, list):
                errors.append(f"interface.{section}: 必须是数组")
                continue
            for index, variable in enumerate(variables):
                prefix = f"interface.{section}[{index}]"
                if not isinstance(variable, dict):
                    errors.append(f"{prefix}: 不是对象")
                    continue
                for field in ("name", "type", "comment", "address"):
                    if field not in variable:
                        errors.append(f"{prefix}: 缺少 {field}")
                if variable.get("type") not in supported_types:
                    errors.append(f"{prefix}.type: 不受 CartGen 支持")
        for index, variable in enumerate(interface.get("local", [])):
            prefix = f"interface.local[{index}]"
            if not isinstance(variable, dict):
                errors.append(f"{prefix}: 不是对象")
                continue
            for field in ("name", "type", "comment"):
                if field not in variable:
                    errors.append(f"{prefix}: 缺少 {field}")
            if variable.get("type") not in supported_types:
                errors.append(f"{prefix}.type: 不受 CartGen 支持")

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
            element_type = el.get("type")
            if element_type in timer_types:
                for field in ("timer_instance", "preset_time"):
                    if not el.get(field):
                        errors.append(f"networks[{i}].elements[{j}]: 缺少 {field}")
                preset_time = el.get("preset_time")
                if preset_time and not time_pattern.fullmatch(preset_time):
                    errors.append(f"networks[{i}].elements[{j}].preset_time: 格式无效")
            elif "operand" not in el:
                errors.append(f"networks[{i}].elements[{j}]: 缺少 operand")

    return errors


# ═══ LadderSpec 安全校验 ═══

def safety_validate_ladder(spec: dict) -> dict:
    """执行 LadderSpec 的语义安全校验。

    此检查是结构 Schema 的下一道硬闸门。它按“每一条驱动电机输出的网络”
    验证急停、过载和正反转互锁，而不是只要在任意网络中出现一次安全触点。
    """
    warnings: list[str] = []
    if not isinstance(spec, dict):
        return {"safe": False, "warnings": ["输入不是 JSON 对象"]}

    interface = spec.get("interface")
    networks = spec.get("networks")
    if not isinstance(interface, dict) or not isinstance(networks, list) or not networks:
        return {"safe": False, "warnings": ["缺少有效的 interface 或 networks"]}

    supported_types = {"Bool", "Int", "Real", "Word"}
    boolean_elements = {"normally_open", "normally_closed", "coil", "coil_set", "coil_reset"}
    timer_elements = {"timer_on_delay", "timer_off_delay"}
    output_coils = {"coil", "coil_set", "coil_reset"}
    time_pattern = re.compile(r"^(?:T#|TIME#)(?:\d+(?:MS|US|NS|D|H|M|S))+$")

    variables: dict[str, dict] = {}
    outputs: set[str] = set()
    for section in ("inputs", "outputs", "local"):
        entries = interface.get(section, [])
        if not isinstance(entries, list):
            warnings.append(f"interface.{section} 必须是数组")
            continue
        for index, variable in enumerate(entries):
            if not isinstance(variable, dict):
                warnings.append(f"interface.{section}[{index}] 不是对象")
                continue
            name = variable.get("name")
            value_type = variable.get("type")
            if not isinstance(name, str) or not name:
                warnings.append(f"interface.{section}[{index}] 缺少变量名")
                continue
            key = name.casefold()
            if key in variables:
                warnings.append(f"变量名重复: {name}")
                continue
            if value_type not in supported_types:
                warnings.append(f"变量 {name} 使用 CartGen 不支持的类型: {value_type}")
            if section in {"inputs", "outputs"} and not variable.get("address"):
                warnings.append(f"I/O 变量 {name} 缺少物理地址映射")
            variables[key] = variable
            if section == "outputs":
                outputs.add(key)

    def _is_estop(name: str) -> bool:
        lowered = name.casefold()
        return "stop" in lowered or "emergency" in lowered

    def _is_overload(name: str) -> bool:
        lowered = name.casefold()
        return "overload" in lowered or "fault" in lowered

    def _is_forward(name: str) -> bool:
        lowered = name.casefold()
        return "fwd" in lowered or "forward" in lowered

    def _is_reverse(name: str) -> bool:
        lowered = name.casefold()
        return "rev" in lowered or "reverse" in lowered

    def _is_motor_output(name: str) -> bool:
        lowered = name.casefold()
        return any(keyword in lowered for keyword in ("motor", "run", "fwd", "forward", "rev", "reverse", "pump", "conveyor"))

    motor_outputs = {name for name in outputs if _is_motor_output(name)}
    forward_outputs = {name for name in motor_outputs if _is_forward(name)}
    reverse_outputs = {name for name in motor_outputs if _is_reverse(name)}
    timer_instances: set[str] = set()

    for network_index, network in enumerate(networks):
        if not isinstance(network, dict):
            warnings.append(f"networks[{network_index}] 不是对象")
            continue
        elements = network.get("elements")
        if not isinstance(elements, list) or not elements:
            warnings.append(f"networks[{network_index}] 缺少元素")
            continue

        normally_closed: set[str] = set()
        driven_motor_outputs: set[str] = set()
        for element_index, element in enumerate(elements):
            if not isinstance(element, dict):
                warnings.append(f"networks[{network_index}].elements[{element_index}] 不是对象")
                continue
            element_type = element.get("type")
            operand = element.get("operand")
            prefix = f"networks[{network_index}].elements[{element_index}]"

            if element_type in timer_elements:
                timer_instance = element.get("timer_instance")
                preset_time = element.get("preset_time")
                if not isinstance(timer_instance, str) or not timer_instance:
                    warnings.append(f"{prefix} 缺少 timer_instance")
                elif timer_instance.casefold() in timer_instances:
                    warnings.append(f"定时器实例重复: {timer_instance}")
                else:
                    timer_instances.add(timer_instance.casefold())
                if not isinstance(preset_time, str) or not time_pattern.fullmatch(preset_time):
                    warnings.append(f"{prefix} 的 preset_time 无效")
                if operand:
                    warnings.append(f"{prefix} 的定时器不得携带会被 CartGen 忽略的 operand")
                continue

            if element_type not in boolean_elements:
                warnings.append(f"{prefix} 使用不支持的元素类型: {element_type}")
                continue
            if not isinstance(operand, str) or not operand:
                warnings.append(f"{prefix} 缺少 operand")
                continue
            operand_key = operand.casefold()
            variable = variables.get(operand_key)
            if variable is None:
                warnings.append(f"{prefix} 引用未声明变量: {operand}")
                continue
            if variable.get("type") != "Bool":
                warnings.append(f"{prefix} 的布尔元件引用了非 Bool 变量: {operand}")
            if element_type == "normally_closed":
                normally_closed.add(operand_key)
            if element_type in output_coils and operand_key in motor_outputs:
                driven_motor_outputs.add(operand_key)

        for output in driven_motor_outputs:
            output_name = variables[output]["name"]
            if not any(_is_estop(name) for name in normally_closed):
                warnings.append(f"网络 {network_index + 1} 驱动 {output_name} 时缺少常闭急停互锁 iStop")
            if not any(_is_overload(name) for name in normally_closed):
                warnings.append(f"网络 {network_index + 1} 驱动 {output_name} 时缺少常闭过载互锁 iOverload")
            if output in forward_outputs and reverse_outputs and not (normally_closed & reverse_outputs):
                warnings.append(f"网络 {network_index + 1} 驱动 {output_name} 时缺少反转输出互锁")
            if output in reverse_outputs and forward_outputs and not (normally_closed & forward_outputs):
                warnings.append(f"网络 {network_index + 1} 驱动 {output_name} 时缺少正转输出互锁")

    if warnings:
        return {"safe": False, "warnings": warnings}
    return {"safe": True}


# ═══ 加载配置 ═══
_config_path = Path(__file__).parent / "config.yaml"
with open(_config_path, encoding="utf-8") as f:
    _raw = yaml.safe_load(f)

cfg = _Config(_raw)


class TargetConfigurationError(RuntimeError):
    """唯一控制目标与 V21/隔离 PLCSIM 契约不一致。"""


@dataclass(frozen=True)
class ControlTarget:
    profile: str
    tia_version: str
    project_path: PureWindowsPath  # 控制目标为 Windows 路径语义，与运行平台无关
    plcsim_instance: str
    plc_ip: str


def _read_attr(value: Any, path: tuple[str, ...]) -> Any:
    for key in path:
        value = getattr(value, key)
    return value


def validate_control_target(config: Any | None = None) -> ControlTarget:
    """验证所有控制入口只能指向已批准的 V21 隔离仿真目标。

    此函数不检查文件是否存在，也不连接设备；调用方必须在任何 TIA/PLCSIM
    动作前调用它，以便把配置漂移作为硬错误处理。
    """
    config = cfg if config is None else config
    try:
        target = config.target
        profile = str(target.profile)
        tia_version = str(target.tia_version).upper()
        project_path = PureWindowsPath(str(target.project_path))
        plcsim_instance = str(target.plcsim_instance)
        plc_ip = str(target.plc_ip)
    except AttributeError as exc:
        raise TargetConfigurationError(f"唯一控制目标缺少字段: {exc}") from exc

    errors: list[str] = []
    if profile != "isolated_plcsim_v21":
        errors.append("target.profile 必须为 isolated_plcsim_v21")
    if tia_version != "V21":
        errors.append("target.tia_version 必须为 V21")
    if project_path.name != "demo_V21.ap21" or project_path.suffix.lower() != ".ap21":
        errors.append("target.project_path 必须指向 demo_V21.ap21")
    if plcsim_instance != "factoryio":
        errors.append("target.plcsim_instance 必须为 factoryio")
    try:
        ipaddress.ip_address(plc_ip)
    except ValueError:
        errors.append("target.plc_ip 不是有效 IP 地址")
    else:
        if plc_ip != "192.168.0.110":
            errors.append("target.plc_ip 必须为隔离 PLCSIM 地址 192.168.0.110")

    aliases = {
        ("tia", "version"): tia_version,
        ("tia", "project_path"): str(project_path),
        ("simulation", "advanced", "plc_ip"): plc_ip,
        ("factory_io", "plcsim_instance"): plcsim_instance,
        ("factory_io", "tcpip", "host"): plc_ip,
    }
    for path, expected in aliases.items():
        try:
            actual = _read_attr(config, path)
        except AttributeError:
            continue
        if str(actual) != expected:
            errors.append(f"{'.'.join(path)} 与唯一 target 配置冲突")

    if errors:
        raise TargetConfigurationError("; ".join(errors))
    return ControlTarget(
        profile=profile,
        tia_version=tia_version,
        project_path=project_path,
        plcsim_instance=plcsim_instance,
        plc_ip=plc_ip,
    )
