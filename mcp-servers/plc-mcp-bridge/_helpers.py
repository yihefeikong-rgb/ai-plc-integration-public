"""共享辅助函数、路径、配置和 MCP 实例"""
import sys
import os
import subprocess
import json
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# ── MCP 实例 ──
mcp = FastMCP("plc_mcp")

# ── 路径 ──
PROJECT_ROOT = Path(__file__).parent.parent.parent
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

PLCSIM_API = TIA_MCP_DIR / "plcsim_api.py"
TIAWORKER_EXE = TIA_MCP_DIR / "bin" / "TiaWorker.exe"
DOWNLOAD_SCRIPT = TIA_MCP_DIR / "download_to_plcsim.py"
P3_SCRIPT = PROJECT_ROOT / "p3_flow.py"

# ── 配置 ──
sys.path.insert(0, str(TIA_MCP_DIR))
try:
    from config_loader import cfg
    PROJECT_PATH = cfg.tia.project_path
    PLC_IP = cfg.simulation.advanced.plc_ip
    PLCSIM_INSTANCE = cfg.factory_io.plcsim_instance
    GOLDEN_ZIP = os.path.join(os.path.dirname(PROJECT_PATH), 'factory_io1_golden.zip')
    STORAGE_PATH = os.path.join(os.path.dirname(PROJECT_PATH), 'plcsim_storage')
except Exception:
    cfg = None
    PROJECT_PATH = ""
    PLC_IP = "192.168.0.1"
    PLCSIM_INSTANCE = "factoryio"
    GOLDEN_ZIP = ""
    STORAGE_PATH = ""


# ── 辅助函数 ──

def _run_python(script: Path, args: list[str], timeout: int = 60) -> dict:
    """运行 Python 脚本子进程，返回解析后的 JSON"""
    cmd = [sys.executable, str(script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding='utf-8', errors='replace')
        out = r.stdout.strip()
        err = r.stderr.strip()
        if out:
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                pass
        return {
            "success": r.returncode == 0,
            "output": out,
            "stderr": err,
            "returncode": r.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _run_tiaworker(command: str, data: dict, timeout: int = 180) -> dict:
    """运行 TiaWorker.exe 子进程"""
    if not TIAWORKER_EXE.exists():
        return {"success": False, "error": f"TiaWorker 未编译: {TIAWORKER_EXE}"}

    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(data, tmp)
    tmp_path = tmp.name
    tmp.close()

    try:
        r = subprocess.run(
            [str(TIAWORKER_EXE), command, tmp_path],
            capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace',
        )
        out = r.stdout.strip()
        if out:
            try:
                result = json.loads(out)
                if result.get('status') == 'ok':
                    return {"success": True, "data": result.get('data', {}), "raw": out}
                else:
                    return {"success": False, "error": result.get('error', '未知错误'), "raw": out}
            except json.JSONDecodeError:
                return {"success": r.returncode == 0, "output": out, "raw": out}
        return {"success": False, "error": "TiaWorker 无输出"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"TiaWorker 超时 ({timeout}s)"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _format_result(success: bool, data=None, error: str = "") -> str:
    """统一格式化返回消息"""
    if success:
        if data:
            return f"✅ 成功\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```"
        return "✅ 成功"
    return f"❌ 失败: {error}"


def _check_project() -> str | None:
    """检查项目路径，返回错误信息或 None"""
    if not PROJECT_PATH or not os.path.exists(PROJECT_PATH):
        return f"❌ 项目文件不存在: {PROJECT_PATH}"
    return None
