import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Settings:
    deepseek_api_key = _env("DEEPSEEK_API_KEY")
    deepseek_base_url = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model_simple = _env("DEEPSEEK_MODEL_SIMPLE", "deepseek-chat")
    deepseek_model_complex = _env("DEEPSEEK_MODEL_COMPLEX", "deepseek-chat")

    opcua_endpoint = _env("OPCUA_ENDPOINT", "opc.tcp://localhost:4840")
    opcua_username = _env("OPCUA_USERNAME", "")
    opcua_password = _env("OPCUA_PASSWORD", "")

    modbus_host = _env("MODBUS_HOST", "localhost")
    modbus_port = int(_env("MODBUS_PORT", "502"))

    melsec_host = _env("MELSEC_HOST", "")
    melsec_port = int(_env("MELSEC_PORT", "5001"))

    influxdb_url = _env("INFLUXDB_URL", "http://localhost:8086")
    influxdb_token = _env("INFLUXDB_TOKEN", "")
    influxdb_org = _env("INFLUXDB_ORG", "ai-plc")
    influxdb_bucket = _env("INFLUXDB_BUCKET", "plc-data")

    safety_write_confirm = _env("SAFETY_WRITE_CONFIRM", "true").lower() == "true"
    safety_audit_log = _env("SAFETY_AUDIT_LOG", "./logs/audit.log")
    safety_max_errors = int(_env("SAFETY_MAX_CONSECUTIVE_ERRORS", "3"))


settings = Settings()
