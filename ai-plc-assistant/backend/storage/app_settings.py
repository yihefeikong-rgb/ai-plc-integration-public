"""应用设置存储 — JSON 文件持久化，支持前端读写"""

import json
import os
import tempfile
from typing import Any, Optional

import keyring

DEFAULT_SETTINGS = {
    "deepseek_api_key": "",
    "deepseek_base_url": "https://api.deepseek.com",
    "deepseek_model": "deepseek-v4-flash",
    "openai_api_key": "",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_model": "gpt-5.5",
    "kimi_api_key": "",
    "kimi_base_url": "https://api.moonshot.ai/v1",
    "kimi_model": "kimi-k2.7-code",
    "claude_api_key": "",
    "claude_base_url": "https://api.anthropic.com",
    "claude_model": "claude-sonnet-4-6",
    "custom_api_key": "",
    "custom_base_url": "",
    "custom_model": "",
    "default_plc_type": "S7-1200",
    "default_tia_version": "V18",
    "default_language": "SCL",
}

MASKED_FIELDS = {
    "deepseek_api_key", "openai_api_key", "kimi_api_key", "claude_api_key", "custom_api_key",
}

KEYRING_SERVICE = "ai-plc-assistant"


class SettingsCredentialError(RuntimeError):
    """系统凭据库不可用时，拒绝把 API Key 回退写入普通 JSON。"""


class AppSettings:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._data: dict = {}

    def initialize(self):
        os.makedirs(os.path.dirname(self.file_path) or ".", exist_ok=True)
        if os.path.exists(self.file_path):
            with open(self.file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = dict(DEFAULT_SETTINGS)

        # 从 .env / config 迁移已有配置。API Key 只进入系统凭据库，
        # 绝不保留在 settings.json 中。
        from config import settings as env_settings
        for key in DEFAULT_SETTINGS:
            if key in MASKED_FIELDS:
                legacy_value = self._data.get(key, "")
                if legacy_value:
                    self._set_credential(key, str(legacy_value))
                    self._data[key] = ""
                env_val = getattr(env_settings, key, "") if hasattr(env_settings, key) else ""
                if env_val and not self._get_credential(key):
                    self._set_credential(key, str(env_val))
                continue
            if not self._data.get(key) and hasattr(env_settings, key):
                env_val = getattr(env_settings, key, "")
                if env_val:
                    self._data[key] = env_val

        self._save()
        return self

    def get_all(self, mask_keys: bool = True) -> dict:
        """获取所有设置，可选遮盖 API Key"""
        result = dict(self._data)
        for field in MASKED_FIELDS:
            val = self._get_credential(field)
            if mask_keys:
                if val and len(val) > 8:
                    result[field] = val[:4] + "*" * (len(val) - 8) + val[-4:]
                elif val:
                    result[field] = "****"
                else:
                    result[field] = ""
            else:
                result[field] = val
        return result

    def get(self, key: str, default: Any = "") -> Any:
        if key in MASKED_FIELDS:
            return self._get_credential(key) or default
        return self._data.get(key, default)

    def update(self, updates: dict) -> dict:
        """更新设置。如果 API Key 是遮盖值（含 *），则跳过不覆盖"""
        for key, val in updates.items():
            if key not in DEFAULT_SETTINGS:
                continue
            # 跳过遮盖的 key（前端没改就不覆盖）
            if key in MASKED_FIELDS and "*" in str(val):
                continue
            if key in MASKED_FIELDS:
                self._set_credential(key, str(val))
                self._data[key] = ""
                continue
            self._data[key] = val
        self._save()
        return self.get_all(mask_keys=True)

    @staticmethod
    def _credential_name(key: str) -> str:
        return f"settings/{key}"

    def _get_credential(self, key: str) -> str:
        try:
            return keyring.get_password(KEYRING_SERVICE, self._credential_name(key)) or ""
        except Exception as exc:
            raise SettingsCredentialError(f"无法读取系统凭据库: {exc}") from exc

    def _set_credential(self, key: str, value: str) -> None:
        try:
            if value:
                keyring.set_password(KEYRING_SERVICE, self._credential_name(key), value)
            else:
                try:
                    keyring.delete_password(KEYRING_SERVICE, self._credential_name(key))
                except keyring.errors.PasswordDeleteError:
                    pass
        except Exception as exc:
            raise SettingsCredentialError(
                "系统凭据库不可用，拒绝将 API Key 写入 settings.json"
            ) from exc

    def _save(self):
        directory = os.path.dirname(self.file_path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, self.file_path)
            try:
                os.chmod(self.file_path, 0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise


# 全局单例
_instance: Optional[AppSettings] = None


def get_settings_store() -> AppSettings:
    global _instance
    return _instance


def set_settings_store(store: AppSettings):
    global _instance
    _instance = store
