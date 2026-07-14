from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_p3_flow_resolves_tia_mcp_from_the_project_root():
    content = (PROJECT_ROOT / "scripts" / "p3_flow.py").read_text(encoding="utf-8")

    assert 'PROJECT_ROOT = SCRIPT_DIR.parent' in content
    assert 'TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"' in content
    assert 'SCRIPT_DIR / "mcp-servers" / "tia-mcp"' not in content


def test_start_bat_stays_at_the_repository_root_and_has_one_mcp_owner():
    content = (PROJECT_ROOT / "start.bat").read_text(encoding="utf-8")

    assert 'cd /d "%~dp0"' in content
    assert 'cd /d "%~dp0.."' not in content
    assert 'MCP 服务器由 backend 内部 orchestrator 独占管理' in content
    assert 'start "orchestrator"' not in content
    assert 'start "backend"' in content
    assert 'start "plc-mcp-bridge"' not in content
    assert 'start "tia-mcp"' not in content
    assert 'start "robot-mcp"' not in content


def test_desktop_backend_port_has_one_contract_at_8005():
    backend_config = (PROJECT_ROOT / "ai-plc-assistant" / "backend" / "config.py").read_text(encoding="utf-8")
    root_start = (PROJECT_ROOT / "start.bat").read_text(encoding="utf-8")
    vite_config = (PROJECT_ROOT / "ai-plc-assistant" / "frontend" / "vite.config.js").read_text(encoding="utf-8")
    frontend_api = (PROJECT_ROOT / "ai-plc-assistant" / "frontend" / "src" / "api.js").read_text(encoding="utf-8")

    assert 'port: int = 8005' in backend_config
    assert 'set BACKEND_PORT=8005' in root_start
    assert "target: 'http://127.0.0.1:8005'" in vite_config
    assert "http://127.0.0.1:8005/api" in frontend_api


def test_desktop_starters_refuse_busy_ports_without_killing_processes():
    for filename in ("start.bat", "start_backend.bat"):
        content = (PROJECT_ROOT / "ai-plc-assistant" / filename).read_text(encoding="utf-8")

        assert "Stop-Process" not in content
        assert "taskkill" not in content.lower()
        assert "Get-NetTCPConnection" in content
        assert "exit /b 1" in content
