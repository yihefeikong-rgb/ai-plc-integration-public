"""当前全链路事实报告测试。"""

from types import SimpleNamespace

import pytest

from scripts import current_chain_report
from scripts import preflight


@pytest.fixture(autouse=True)
def _offline_report_probes(monkeypatch):
    def passed(name):
        result = preflight.CheckResult(name)
        result.passed = True
        result.detail = "offline stub"
        return result

    for function_name in (
        "check_tia_portal",
        "check_plcsim_api",
        "check_deepseek_api_key",
        "check_python_dependencies",
        "check_factory_io",
        "check_ports",
    ):
        monkeypatch.setattr(
            current_chain_report.preflight,
            function_name,
            lambda name=function_name: passed(name),
        )
    monkeypatch.setattr(current_chain_report, "_port_open", lambda port: False)
    monkeypatch.setattr(current_chain_report, "_check_dependencies", lambda: {})


def test_report_contains_chain_facts():
    report = current_chain_report.build_report()

    assert report["tia"]["project_path"]
    assert report["tia"]["device_name"] == "S7-1500/ET200MP station_1"
    assert report["plcsim"]["instance_name"] == "factoryio"
    assert report["plcsim"]["plc_ip"]
    assert "factory_io" in report
    assert "${" not in report["factory_io"]["exe_path"]
    assert "ports" in report
    assert "dependencies" in report


def test_report_explains_blockers():
    report = current_chain_report.build_report()

    assert isinstance(report["blockers"], list)
    assert all("name" in item and "suggestion" in item for item in report["blockers"])


def test_report_ignores_legacy_plc_ip_override(monkeypatch):
    monkeypatch.setenv("S7_PLC_IP", "203.0.113.77")
    monkeypatch.setenv("PLCSIM_TARGET_IP", "203.0.113.78")
    monkeypatch.setattr(
        current_chain_report,
        "get_control_target",
        lambda: SimpleNamespace(
            project_path=r"D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\demo_V21.ap21",
            tia_version="V21",
            plc_ip="192.168.0.1",
            plcsim_instance="factoryio",
            device_name="S7-1500/ET200MP station_1",
        ),
    )

    report = current_chain_report.build_report()

    assert report["plcsim"]["plc_ip"] == "192.168.0.1"


def test_report_fails_closed_on_target_drift(monkeypatch):
    def reject_target():
        raise current_chain_report.TargetConfigurationError("target.plc_ip 漂移")

    monkeypatch.setattr(current_chain_report, "get_control_target", reject_target)

    report = current_chain_report.build_report()

    assert report["plcsim"]["plc_ip"] == ""
    assert report["plcsim"]["instance_name"] == ""
    assert report["blockers"][0]["name"] == "唯一控制目标"
