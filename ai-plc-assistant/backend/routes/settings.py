"""设置 API — 前端读写 + 模型测试"""

import time
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security import require_local_session
from storage.app_settings import get_settings_store

router = APIRouter()

PROVIDER_MODELS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "default": "deepseek-v4-flash",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-5.5", "gpt-5.5-pro", "gpt-5.4-mini", "gpt-5.4-nano", "gpt-4.1", "gpt-4.1-mini"],
        "default": "gpt-5.5",
    },
    "kimi": {
        "label": "Kimi (月之暗面)",
        "base_url": "https://api.moonshot.ai/v1",
        "models": ["kimi-k2.7-code", "kimi-k2.7-code-highspeed", "kimi-k2.6", "kimi-k2.5", "moonshot-v1-128k"],
        "default": "kimi-k2.7-code",
    },
    "claude": {
        "label": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com",
        "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
        "default": "claude-sonnet-4-6",
    },
    "custom": {
        "label": "自定义模型",
        "base_url": "",
        "models": [],
        "default": "",
    },
}

TRUSTED_BASE_URLS = {
    config["base_url"]
    for config in PROVIDER_MODELS.values()
    if config["base_url"]
}


def _validate_base_urls(updates: dict[str, str], store) -> None:
    for key, value in updates.items():
        if not key.endswith("_base_url") or not value:
            continue
        parsed = urlparse(value)
        if parsed.scheme != "https" or value not in TRUSTED_BASE_URLS:
            raise HTTPException(status_code=422, detail="模型服务地址不在 HTTPS 白名单中")
        api_key_name = key.replace("_base_url", "_api_key")
        if value != store.get(key) and store.get(api_key_name) and not updates.get(api_key_name):
            raise HTTPException(status_code=422, detail="修改模型服务地址时必须重新提供 API Key")


class SettingsUpdate(BaseModel):
    deepseek_api_key: str = ""
    deepseek_base_url: str = ""
    deepseek_model: str = ""
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    kimi_api_key: str = ""
    kimi_base_url: str = ""
    kimi_model: str = ""
    claude_api_key: str = ""
    claude_base_url: str = ""
    claude_model: str = ""
    custom_api_key: str = ""
    custom_base_url: str = ""
    custom_model: str = ""
    default_plc_type: str = ""
    default_tia_version: str = ""
    default_language: str = ""


@router.get("")
async def get_settings():
    store = get_settings_store()
    if store is None:
        raise HTTPException(status_code=503, detail="设置存储未初始化")
    return {"settings": store.get_all(mask_keys=True)}


@router.put("")
async def update_settings(data: SettingsUpdate, _: None = Depends(require_local_session)):
    store = get_settings_store()
    if store is None:
        raise HTTPException(status_code=503, detail="设置存储未初始化")
    updates = {k: v for k, v in data.model_dump().items() if v}
    _validate_base_urls(updates, store)
    result = store.update(updates)
    return {"settings": result, "status": "saved"}


@router.get("/providers")
async def get_providers():
    return {"providers": PROVIDER_MODELS}


@router.post("/test/{provider}")
async def test_provider(provider: str, _: None = Depends(require_local_session)):
    store = get_settings_store()
    if store is None:
        raise HTTPException(status_code=503, detail="设置存储未初始化")

    api_key = store.get(f"{provider}_api_key")
    base_url = store.get(f"{provider}_base_url")
    model = store.get(f"{provider}_model")

    if not api_key:
        return {"status": "error", "message": "未配置 API Key"}
    if not model:
        return {"status": "error", "message": "未选择模型"}

    try:
        t0 = time.time()

        if provider == "claude":
            # Anthropic SDK
            from anthropic import Anthropic
            client = Anthropic(api_key=api_key, timeout=15)
            resp = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}],
            )
            content = resp.content[0].text or ""
        else:
            # OpenAI 兼容
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=10,
            )
            content = resp.choices[0].message.content or ""

        elapsed = round((time.time() - t0) * 1000)
        return {
            "status": "ok",
            "message": f"连接成功 ({elapsed}ms)",
            "model": model,
            "reply": content[:50],
            "latency_ms": elapsed,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
