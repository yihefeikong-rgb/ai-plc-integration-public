"""应用设置存储 — JSON 文件持久化，支持前端读写"""

import json
import os
from typing import Any, Optional

DEFAULT_SETTINGS = {
    "deepseek_api_key": "",
    "deepseek_base_url": "https://api.deepseek.com/v1",
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

        # 从 .env / config 迁移已有的 key
        from config import settings as env_settings
        for key in DEFAULT_SETTINGS:
            if not self._data.get(key) and hasattr(env_settings, key):
                env_val = getattr(env_settings, key, "")
                if env_val:
                    self._data[key] = env_val

        self._save()
        return self

    def get_all(self, mask_keys: bool = True) -> dict:
        """获取所有设置，可选遮盖 API Key"""
        result = dict(self._data)
        if mask_keys:
            for field in MASKED_FIELDS:
                val = result.get(field, "")
                if val and len(val) > 8:
                    result[field] = val[:4] + "*" * (len(val) - 8) + val[-4:]
                elif val:
                    result[field] = "****"
        return result

    def get(self, key: str, default: Any = "") -> Any:
        return self._data.get(key, default)

    def update(self, updates: dict) -> dict:
        """更新设置。如果 API Key 是遮盖值（含 *），则跳过不覆盖"""
        for key, val in updates.items():
            if key not in DEFAULT_SETTINGS:
                continue
            # 跳过遮盖的 key（前端没改就不覆盖）
            if key in MASKED_FIELDS and "*" in str(val):
                continue
            self._data[key] = val
        self._save()
        return self.get_all(mask_keys=True)

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)


# 全局单例
_instance: Optional[AppSettings] = None


def get_settings_store() -> AppSettings:
    global _instance
    return _instance


def set_settings_store(store: AppSettings):
    global _instance
    _instance = store
