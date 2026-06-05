"""
CartGen 测试套件 — 验证所有 LAD 模板能正确生成 SimaticML XML。

用法:
    pytest mcp-servers/tia-mcp/test_cartgen.py -v
    或
    python mcp-servers/tia-mcp/test_cartgen.py
"""
import json
import os
import subprocess
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "templates")
CARTGEN_PROJ = os.path.join(SCRIPT_DIR, "CartGen", "CartGen.csproj")

# 有效元素类型
VALID_TYPES = {"normally_open", "normally_closed", "coil", "coil_set", "coil_reset"}


def get_templates() -> list:
    """获取所有模板文件路径。"""
    if not os.path.isdir(TEMPLATE_DIR):
        return []
    return sorted([
        f for f in os.listdir(TEMPLATE_DIR)
        if f.endswith(".json")
    ])


def validate_spec(spec: dict) -> list:
    """校验 LadderSpec JSON 结构，返回错误列表。"""
    errors = []

    if not isinstance(spec, dict):
        return ["根元素不是 JSON 对象"]

    if "blockName" not in spec:
        errors.append("缺少 blockName")
    if "blockNumber" not in spec:
        errors.append("缺少 blockNumber")

    interface = spec.get("interface", {})
    if not isinstance(interface, dict):
        errors.append("interface 不是对象")
    else:
        for io_type in ("inputs", "outputs", "local"):
            items = interface.get(io_type, [])
            if not isinstance(items, list):
                errors.append(f"interface.{io_type} 不是数组")
                continue
            for i, item in enumerate(items):
                if "name" not in item:
                    errors.append(f"interface.{io_type}[{i}] 缺少 name")
                if "type" not in item:
                    errors.append(f"interface.{io_type}[{i}] 缺少 type")

    networks = spec.get("networks", [])
    if not isinstance(networks, list):
        errors.append("networks 不是数组")
    elif len(networks) == 0:
        errors.append("networks 为空")

    for ni, net in enumerate(networks):
        if not isinstance(net, dict):
            errors.append(f"networks[{ni}] 不是对象")
            continue
        elements = net.get("elements", [])
        if not isinstance(elements, list):
            errors.append(f"networks[{ni}].elements 不是数组")
            continue
        for ei, el in enumerate(elements):
            if "type" not in el:
                errors.append(f"networks[{ni}].elements[{ei}] 缺少 type")
            elif el["type"] not in VALID_TYPES:
                errors.append(
                    f"networks[{ni}].elements[{ei}].type='{el['type']}' "
                    f"无效，允许: {', '.join(sorted(VALID_TYPES))}"
                )
            if "operand" not in el:
                errors.append(f"networks[{ni}].elements[{ei}] 缺少 operand")

    return errors


def test_templates_exist():
    """测试: 模板目录存在且有 JSON 文件。"""
    assert os.path.isdir(TEMPLATE_DIR), f"模板目录不存在: {TEMPLATE_DIR}"
    templates = get_templates()
    assert len(templates) >= 18, f"模板数量不足: {len(templates)}（期望 >=18）"


def test_all_template_specs():
    """测试: 所有模板 JSON 结构合法。"""
    templates = get_templates()
    failed = []
    for t in templates:
        path = os.path.join(TEMPLATE_DIR, t)
        with open(path, encoding="utf-8") as f:
            spec = json.load(f)
        errors = validate_spec(spec)
        if errors:
            failed.append((t, errors))
    assert not failed, f"模板校验失败: {failed}"


def test_all_template_cartgen():
    """测试: 所有模板能被 CartGen 正确生成 XML。"""
    templates = get_templates()
    failed = []
    for t in templates:
        path = os.path.join(TEMPLATE_DIR, t)
        xml_path = path.replace(".json", ".xml")

        r = subprocess.run(
            ["dotnet", "run", "--project", CARTGEN_PROJ, "--", path],
            capture_output=True, text=True, timeout=30,
        )

        success = r.returncode == 0 and os.path.exists(xml_path)

        if success:
            size = os.path.getsize(xml_path)
            assert size > 1000, f"{t}: XML 太小 ({size} bytes)"
            os.unlink(xml_path)
        else:
            err = r.stderr[:300] if r.stderr else r.stdout[:300]
            failed.append(f"{t}: {err}")

    assert not failed, f"CartGen 失败:\n" + "\n".join(failed)


def test_cartgen_build():
    """测试: CartGen 项目编译无错误。"""
    r = subprocess.run(
        ["dotnet", "build", CARTGEN_PROJ, "-c", "Release", "--nologo", "-v", "q"],
        capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, f"CartGen 编译失败 exit={r.returncode}:\n{r.stderr or r.stdout}"
    dll = os.path.join(SCRIPT_DIR, "CartGen", "bin", "Release", "net8.0", "CartGen.dll")
    assert os.path.exists(dll), f"CartGen DLL 未生成: {dll}"


def test_template_count():
    """测试: 模板数量符合预期。"""
    count = len(get_templates())
    print(f"\n  模板总数: {count}")
    assert count >= 18


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
