import importlib.util
import sys
import types
from pathlib import Path

import pytest


def load_download_module():
    path = Path(__file__).with_name("download_to_plcsim.py")
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("target_identity_download", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def configure(module):
    module.cfg = types.SimpleNamespace(
        simulation=types.SimpleNamespace(
            backend="advanced",
            advanced=types.SimpleNamespace(plc_ip="192.168.0.1"),
        ),
        factory_io=types.SimpleNamespace(plcsim_instance="factoryio"),
    )
    module.validate_control_target = lambda: types.SimpleNamespace(
        project_path=Path(r"D:\PLC\demo_V21\demo_V21.ap21"),
        plc_ip="192.168.0.1",
        plcsim_instance="factoryio",
        device_name="S7-1500/ET200MP station_1",
    )


def test_verified_target_accepts_only_the_configured_single_instance(monkeypatch):
    module = load_download_module()
    configure(module)
    monkeypatch.setitem(sys.modules, "plcsim_api", types.SimpleNamespace(
        get_instances=lambda: [{"name": "factoryio", "state": "run"}],
    ))

    assert module._verified_plcsim_target() == "192.168.0.1"


@pytest.mark.parametrize("instances", [[], [{"name": "other", "state": "run"}], [
    {"name": "factoryio", "state": "run"}, {"name": "other", "state": "run"},
]])
def test_verified_target_rejects_missing_ambiguous_or_unexpected_instances(monkeypatch, instances):
    module = load_download_module()
    configure(module)
    monkeypatch.setitem(sys.modules, "plcsim_api", types.SimpleNamespace(
        get_instances=lambda: instances,
    ))

    with pytest.raises(ValueError, match="PLCSIM"):
        module._verified_plcsim_target()


def test_verified_target_rejects_a_free_target_ip(monkeypatch):
    module = load_download_module()
    configure(module)
    monkeypatch.setitem(sys.modules, "plcsim_api", types.SimpleNamespace(
        get_instances=lambda: [{"name": "factoryio", "state": "run"}],
    ))

    with pytest.raises(ValueError, match="配置目标"):
        module._verified_plcsim_target("10.0.0.2")


def test_tiaworker_payload_uses_the_configured_s7_1500_device():
    module = load_download_module()
    configure(module)

    payload = module._build_tiaworker_download_input(
        "192.168.0.1", 180, "download-test"
    )

    assert payload["TargetIp"] == "192.168.0.1"
    assert payload["DeviceName"] == "S7-1500/ET200MP station_1"
    assert payload["ProjectPath"].endswith("demo_V21.ap21")
