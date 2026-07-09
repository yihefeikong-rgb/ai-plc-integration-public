"""preflight 脚本的轻量回归测试。"""

from scripts import preflight


def test_python_dependencies_use_import_module_names():
    """PyPI 包名和 import 名不一致时不应误报缺失。"""
    result = preflight.check_python_dependencies()

    assert result.passed is True
    assert "python-snap7" not in result.detail
    assert "pyyaml" not in result.detail

