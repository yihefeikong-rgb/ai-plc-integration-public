"""Pipeline API 测试 — /api/pipeline/nl-to-sim。"""

from unittest.mock import AsyncMock, MagicMock, patch


def _control_headers(monkeypatch):
    monkeypatch.setenv("LOCAL_API_TOKEN", "pipeline-test-token")
    return {"X-Local-Api-Token": "pipeline-test-token"}


class TestNlToSimPipeline:
    def test_nl_to_sim_route_runs_unified_workflow(self, client, monkeypatch):
        from orchestrator.core import StepResult, WorkflowResult

        mock_result = WorkflowResult(
            workflow_name="nl_to_plcsim_pipeline",
            ok=True,
            steps=[
                StepResult(
                    tool="tia-mcp.create_ladder_block",
                    ok=True,
                    data={"blockName": "MotorFwdRev", "networks": 3},
                    duration_ms=12.0,
                ),
                StepResult(
                    tool="plc-mcp-bridge.s7_read",
                    ok=True,
                    data="M0.0 = False",
                    duration_ms=3.0,
                ),
            ],
            total_duration_ms=20.0,
        )
        mock_engine = MagicMock()
        mock_engine.run_async = AsyncMock(return_value=mock_result)

        with patch("routes.pipeline.get_engine", return_value=mock_engine):
            res = client.post("/api/pipeline/nl-to-sim", json={
                "description": "三相异步电机正反转带急停和过载保护",
                "block_name": "MotorFwdRev",
                "launch_fio": False,
            }, headers=_control_headers(monkeypatch))

        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["workflow_name"] == "nl_to_plcsim_pipeline"
        assert data["steps"][0]["name"] == "生成梯形图块"
        assert data["snap7"]["verified"] is True
        mock_engine.run_async.assert_awaited_once()
        _, kwargs = mock_engine.run_async.await_args
        assert kwargs["input"] == {
            "description": "三相异步电机正反转带急停和过载保护",
            "block_name": "MotorFwdRev",
            "launch_fio": False,
            "authenticated_operator": kwargs["input"]["authenticated_operator"],
        }
        assert kwargs["input"]["authenticated_operator"].startswith("local-session:")

    def test_nl_to_sim_rejects_empty_description(self, client, monkeypatch):
        res = client.post("/api/pipeline/nl-to-sim", json={"description": ""}, headers=_control_headers(monkeypatch))

        assert res.status_code == 400

    def test_nl_to_sim_rejects_unsupported_target_overrides(self, client, monkeypatch):
        res = client.post("/api/pipeline/nl-to-sim", json={
            "description": "电机启停",
            "project_path": "D:/untrusted/demo.ap21",
            "plc_ip": "10.0.0.2",
        }, headers=_control_headers(monkeypatch))

        assert res.status_code == 422
