"""当前全链路事实报告测试。"""

from scripts.current_chain_report import build_report


def test_report_contains_chain_facts():
    report = build_report()

    assert report["tia"]["project_path"]
    assert report["plcsim"]["instance_name"] == "factoryio"
    assert report["plcsim"]["plc_ip"]
    assert "factory_io" in report
    assert "${" not in report["factory_io"]["exe_path"]
    assert "ports" in report
    assert "dependencies" in report


def test_report_explains_blockers():
    report = build_report()

    assert isinstance(report["blockers"], list)
    assert all("name" in item and "suggestion" in item for item in report["blockers"])
