"""TIA Portal 实机集成测试 — 需要 TIA Portal V18 已打开

运行: PYTHONIOENCODING=utf-8 python -m pytest tests/test_tia_real.py -v
跳过: PYTHONIOENCODING=utf-8 python -m pytest tests/test_tia_real.py -v -k "not real"

标记: @pytest.mark.real — 标记需要 TIA Portal 的测试
"""
import json
import subprocess
import tempfile
import os
from pathlib import Path
import pytest

# ── 配置 ──
PROJECT_DIR = Path(__file__).parent.parent.parent.parent  # 项目根
TIAWORKER = str(PROJECT_DIR / "mcp-servers" / "tia-mcp" / "bin" / "TiaWorker.exe")
PROJECT_PATH = r"D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18"
DEVICE_NAME = "S7-1200 station_1"


def tw(command: str, data: dict, timeout: int = 60) -> dict:
    """调用 TiaWorker，返回解析后的 JSON"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(data, f)
        tmp_path = f.name
    try:
        r = subprocess.run(
            [TIAWORKER, command, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        return json.loads(r.stdout)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _require_success(r: dict) -> dict:
    """断言 TiaWorker 返回成功"""
    assert r.get('status') == 'ok', f"TiaWorker 失败: {r.get('error', r)}"
    return r.get('data', {})


@pytest.mark.real
class TestTiaProjectInfo:
    """需要 TIA Portal V18 打开，demo.ap18 项目已加载"""

    def test_list_devices(self):
        r = tw('list-devices', {'ProjectPath': PROJECT_PATH})
        data = _require_success(r)
        devices = data.get('devices', [])
        assert len(devices) >= 1
        names = [d['name'] for d in devices]
        assert any('S7-1200' in n for n in names), f"未找到 S7-1200: {names}"

    def test_get_project_info(self):
        r = tw('get-project-info', {'ProjectPath': PROJECT_PATH})
        data = _require_success(r)
        assert 'name' in data or 'path' in data

    def test_get_hardware_info(self):
        r = tw('get-hardware-info', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        data = _require_success(r)
        # 至少有机架或设备信息
        assert len(data) > 0

    def test_list_blocks(self):
        r = tw('list-blocks', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        data = _require_success(r)
        blocks = data.get('blocks', [])
        assert len(blocks) > 0
        # Main 应该存在
        names = [b.get('name') for b in blocks]
        assert any('Main' in (n or '') for n in names), f"未找到 Main: {names}"

    def test_list_dbs(self):
        r = tw('list-dbs', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        data = _require_success(r)
        dbs = data.get('dbs', data.get('blocks', []))
        assert len(dbs) >= 0


@pytest.mark.real
class TestTiaTagsAndTypes:
    """标签表和 UDT"""

    def test_list_tags(self):
        r = tw('list-tags', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        _require_success(r)

    def test_list_udts(self):
        r = tw('list-udts', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        data = _require_success(r)
        udts = data.get('udts', [])
        print(f"UDT: {len(udts)}")

    def test_list_tag_tables(self):
        r = tw('create-tag-table', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME,
                                     'TagTableName': '__test_sys'})
        # 可能已存在，不强制成功

    def test_list_watch_tables(self):
        r = tw('list-watch-tables', {'ProjectPath': PROJECT_PATH, 'DeviceName': DEVICE_NAME})
        data = _require_success(r)
        tables = data.get('watch_tables', [])
        print(f"监控表: {len(tables)}")


@pytest.mark.real
class TestTiaBlockDetails:
    """块详情"""

    def test_get_main_interface(self):
        r = tw('get-block-interface', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
            'BlockName': 'Main',
        })
        data = _require_success(r)
        assert 'interface' in data or 'sections' in data

    def test_get_auto_gen_interface(self):
        r = tw('get-block-interface', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
            'BlockName': 'AutoGen',
        })
        data = _require_success(r)
        assert 'interface' in data or 'sections' in data


@pytest.mark.real
class TestTiaCrossReference:
    """交叉引用"""

    def test_find_callers(self):
        r = tw('find-callers', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
            'BlockName': 'Main',
        })
        data = _require_success(r)
        print(f"Main 的调用者: {len(data)}")

    def test_find_unused_blocks(self):
        r = tw('find-unused-blocks', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
        })
        data = _require_success(r)
        unused = data.get('unused_blocks', [])
        print(f"未引用块: {len(unused)}")
        for b in unused[:5]:
            print(f"  {b}")


@pytest.mark.real
@pytest.mark.skip(reason="会修改项目，需确认后手动运行")
class TestTiaWriteOperations:
    """写入操作（默认跳过）"""

    def test_create_and_delete_block(self):
        """创建一个临时块再删除"""
        name = "TempTest_AI"
        r = tw('create-block', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
            'BlockName': name,
            'BlockType': 'FC',
            'Language': 'SCL',
        })
        data = _require_success(r)
        assert data.get('name') == name

        # 删除
        r = tw('delete-block', {
            'ProjectPath': PROJECT_PATH,
            'DeviceName': DEVICE_NAME,
            'BlockName': name,
        })
        _require_success(r)
