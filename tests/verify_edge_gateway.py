# ── EdgeGateway 全链路验证脚本 ──
# 在没有 Docker 的情况下，验证 EdgeGateway 各组件可独立运行。
# 需要：Python 3.11+、DeepSeek API Key

import sys, json, asyncio, os
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "edge-gateway" / "src"))

# Mock mcp_common
from unittest.mock import MagicMock, AsyncMock
import mcp_common
mcp_common.config = MagicMock()
mcp_common.audit = MagicMock()

# 设置环境变量
os.environ.setdefault("DEEPSEEK_API_KEY", "")
os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
os.environ.setdefault("DEEPSEEK_MODEL_SIMPLE", "deepseek-chat")
os.environ.setdefault("DEEPSEEK_MODEL_COMPLEX", "deepseek-chat")
os.environ.setdefault("INFLUXDB_URL", "http://localhost:8086")
os.environ.setdefault("INFLUXDB_TOKEN", "test-token")
os.environ.setdefault("INFLUXDB_ORG", "ai-plc")
os.environ.setdefault("INFLUXDB_BUCKET", "plc-data")

CHECKS = []
PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")
    CHECKS.append((name, condition, detail))


async def run_all_checks():
    print("=" * 60)
    print("EdgeGateway 全链路验证")
    print("=" * 60)

    # 1. 组件导入检查
    print("\n[1/6] 组件导入")
    try:
        from change_detector import has_significant_change, is_out_of_bounds
        check("change_detector 导入成功", True)
    except Exception as e:
        check("change_detector 导入成功", False, str(e))

    try:
        from app import EdgeGateway
        check("EdgeGateway 导入成功", True)
    except Exception as e:
        check("EdgeGateway 导入成功", False, str(e))

    try:
        from ai_client import ai
        check("ai_client 导入成功", True)
    except Exception as e:
        check("ai_client 导入成功", False, str(e))

    # 2. change_detector 功能
    print("\n[2/6] change_detector 功能")
    config = [{"tag": "T1", "threshold": {"min": 0, "max": 100, "delta": 10}}]
    check("首次读取视为变化", has_significant_change("T1", 50, {}, config))
    check("相同值不是变化", not has_significant_change("T1", 50, {"T1": 50}, config))
    check("超 max 检测", is_out_of_bounds("T1", 101, config))
    check("在范围内不超限", not is_out_of_bounds("T1", 50, config))

    # 3. EdgeGateway 初始化
    print("\n[3/6] EdgeGateway 初始化")
    gw = EdgeGateway()
    check("默认标签加载", len(gw.tag_config) == 4, f"got {len(gw.tag_config)}")
    check("扫描间隔默认 30s", gw.scan_interval == 30)
    check("初始未运行", gw.running is False)
    check("初始未熔断", gw._ai_fused is False)

    # 4. EdgeGateway 扫描
    print("\n[4/6] EdgeGateway 数据扫描")
    async def mock_read(tag: str) -> dict:
        vals = {"M0.0": {"value": True}, "M0.1": {"value": False},
                "MW10": {"value": 75}, "MW12": {"value": 1500}}
        return vals.get(tag, {"value": None})

    results = await gw.scan_once(mock_read)
    check("扫描返回 4 个结果", len(results) == 4, f"got {len(results)}")
    check("M0.0 值为 True", results[0]["value"] is True)
    check("MW10 值为 75", results[2]["value"] == 75)
    all_ok = all(r["status"] == "ok" for r in results)
    check("全部状态 ok", all_ok)

    # 5. AI 客户端
    print("\n[5/6] AI 客户端（需 API Key）")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        try:
            resp = await ai.chat([{"role": "user", "content": "回复 OK"}])
            check("AI 聊天成功", "OK" in resp.upper(), resp[:50])
        except Exception as e:
            check("AI 聊天成功", False, str(e)[:100])
    else:
        print("  ⏭️  跳过 AI 测试（未设置 DEEPSEEK_API_KEY）")

    # 6. Docker/InfluxDB/Grafana 环境
    print("\n[6/6] 基础设施")
    import subprocess
    try:
        subprocess.run(["docker", "--version"], capture_output=True, check=True)
        check("Docker 已安装", True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        check("Docker 已安装", False, "docker 命令未找到 — 请安装 Docker Desktop")

    # 汇总
    print("\n" + "=" * 60)
    print(f"结果: {PASS} 通过 / {FAIL} 失败 / {PASS+FAIL} 总计")
    print("=" * 60)
    return FAIL == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_checks())
    sys.exit(0 if success else 1)