"""模型管理路由"""

from fastapi import APIRouter, HTTPException

router = APIRouter()

def _get_available_models():
    """根据设置中是否配置了 API Key 来判断模型是否启用"""
    from storage.app_settings import get_settings_store
    store = get_settings_store()
    models = [
        {"id": "deepseek", "name": "DeepSeek", "key_field": "deepseek_api_key"},
        {"id": "openai", "name": "OpenAI", "key_field": "openai_api_key"},
        {"id": "kimi", "name": "Kimi", "key_field": "kimi_api_key"},
        {"id": "claude", "name": "Claude", "key_field": "claude_api_key"},
        {"id": "custom", "name": "自定义", "key_field": "custom_api_key"},
    ]
    result = []
    for m in models:
        enabled = bool(store and store.get(m["key_field"]))
        result.append({"id": m["id"], "name": m["name"], "enabled": enabled})
    return result


@router.get("")
async def list_models():
    """获取可用模型列表（根据 API Key 是否配置判断启用状态）"""
    return {"models": _get_available_models()}


@router.get("/{model_id}")
async def get_model(model_id: str):
    for m in _get_available_models():
        if m["id"] == model_id:
            return {"model": m}
    raise HTTPException(status_code=404, detail=f"模型 {model_id} 不存在")
