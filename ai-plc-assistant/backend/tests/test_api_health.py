"""API 测试 — /api/health"""


class TestHealth:
    def test_health_check(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"

    def test_direct_run_reload_disabled_by_default(self):
        """直跑入口的热重载必须由 AI_PLC_DEV_RELOAD=1 显式门控，默认关闭。"""
        from pathlib import Path
        source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
        assert "reload=True" not in source
        assert "AI_PLC_DEV_RELOAD" in source
