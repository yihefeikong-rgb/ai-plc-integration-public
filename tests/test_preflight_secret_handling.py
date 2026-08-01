from types import SimpleNamespace

from scripts import preflight

def test_preflight_hides_environment_api_key(monkeypatch):
    secret = "environment-secret-value"
    monkeypatch.setenv("DEEPSEEK_API_KEY", secret)

    result = preflight.check_deepseek_api_key()

    assert result.passed is True
    assert secret not in result.detail
    assert secret[:6] not in result.detail
    assert secret[-4:] not in result.detail


def test_preflight_hides_dotenv_api_key(monkeypatch):
    secret = "dotenv-secret-value"
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(preflight, "_read_dotenv_value", lambda key: secret)

    result = preflight.check_deepseek_api_key()

    assert result.passed is True
    assert secret not in result.detail
    assert secret[:6] not in result.detail
    assert secret[-4:] not in result.detail


def test_preflight_requires_a_working_plcsim_api(monkeypatch):
    monkeypatch.setattr(preflight.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="failed"),
    )

    result = preflight.check_plcsim_api()

    assert result.passed is False
    assert "API 查询失败" in result.detail


def test_preflight_accepts_a_queryable_plcsim_api(monkeypatch):
    monkeypatch.setattr(preflight.os.path, "isdir", lambda path: True)
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="无运行实例", stderr=""),
    )

    result = preflight.check_plcsim_api()

    assert result.passed is True
    assert "API 查询成功" in result.detail
