"""LLM 调用服务 — 支持 OpenAI 兼容接口 + Anthropic Claude"""

from openai import OpenAI
from storage.app_settings import get_settings_store


def _get_provider_config(provider: str) -> dict:
    store = get_settings_store()
    if store is None:
        return {"api_key": "", "base_url": "", "model": ""}
    return {
        "api_key": store.get(f"{provider}_api_key", ""),
        "base_url": store.get(f"{provider}_base_url", ""),
        "model": store.get(f"{provider}_model", ""),
    }


def chat(
    model_id: str = "deepseek",
    messages: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    if messages is None:
        messages = []

    provider_map = {
        "deepseek": "deepseek",
        "openai": "openai",
        "gpt": "openai",
        "kimi": "kimi",
        "claude": "claude",
        "custom": "custom",
    }
    provider = provider_map.get(model_id, model_id)
    cfg = _get_provider_config(provider)

    if not cfg["api_key"]:
        raise ValueError(f"模型 {model_id} 未配置 API Key，请在设置中配置")

    # Claude 使用 Anthropic SDK
    if provider == "claude":
        return _call_anthropic(cfg, messages, temperature, max_tokens)

    # 其余走 OpenAI 兼容接口
    return _call_openai_compatible(cfg, messages, temperature, max_tokens)


def _call_openai_compatible(cfg: dict, messages: list, temperature: float, max_tokens: int) -> str:
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    response = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("模型返回了空回复")
    return content


def _call_anthropic(cfg: dict, messages: list, temperature: float, max_tokens: int) -> str:
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("请安装 anthropic SDK: pip install anthropic")

    client = Anthropic(api_key=cfg["api_key"])

    # 分离 system prompt 和对话消息
    system_text = ""
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
        else:
            chat_messages.append({"role": m["role"], "content": m["content"]})

    if not chat_messages:
        chat_messages = [{"role": "user", "content": "hello"}]

    kwargs = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "messages": chat_messages,
        "temperature": temperature,
    }
    if system_text:
        kwargs["system"] = system_text

    response = client.messages.create(**kwargs)
    content = response.content[0].text
    if content is None:
        raise ValueError("Claude 返回了空回复")
    return content


PROVIDER_ORDER = ["deepseek", "openai", "kimi", "claude", "custom"]


def get_available_providers() -> list[str]:
    """获取所有已配置 API Key 的提供商"""
    store = get_settings_store()
    if store is None:
        return []
    return [p for p in PROVIDER_ORDER if store.get(f"{p}_api_key")]


def chat_with_fallback(
    model_id: str = "deepseek",
    messages: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> dict:
    """带自动切换的聊天 — 主模型失败时尝试下一个

    Returns:
        {"content": str, "model": str, "fallback": bool}
    """
    if messages is None:
        messages = []

    # 先尝试指定模型
    try:
        content = chat(model_id, messages, temperature, max_tokens)
        return {"content": content, "model": model_id, "fallback": False}
    except Exception as primary_err:
        pass

    # 主模型失败 → 尝试其他已配置模型
    available = get_available_providers()
    provider_map = {"deepseek": "deepseek", "openai": "openai", "kimi": "kimi", "claude": "claude", "custom": "custom"}
    tried = {provider_map.get(model_id, model_id)}

    for provider in available:
        if provider in tried:
            continue
        tried.add(provider)
        try:
            content = chat(provider, messages, temperature, max_tokens)
            return {"content": content, "model": provider, "fallback": True}
        except Exception:
            continue

    # 全部失败
    raise ValueError(f"所有模型调用均失败。主模型 {model_id}: {primary_err}")


# ---- Streaming ----


def chat_stream(
    model_id: str = "deepseek",
    messages: list[dict] | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
):
    """流式调用 LLM — 逐 token yield"""
    if messages is None:
        messages = []

    provider_map = {
        "deepseek": "deepseek", "openai": "openai", "gpt": "openai",
        "kimi": "kimi", "claude": "claude", "custom": "custom",
    }
    provider = provider_map.get(model_id, model_id)
    cfg = _get_provider_config(provider)

    if not cfg["api_key"]:
        raise ValueError(f"模型 {model_id} 未配置 API Key，请在设置中配置")

    if provider == "claude":
        yield from _stream_anthropic(cfg, messages, temperature, max_tokens)
    else:
        yield from _stream_openai_compatible(cfg, messages, temperature, max_tokens)


def _stream_openai_compatible(cfg: dict, messages: list, temperature: float, max_tokens: int):
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    response = client.chat.completions.create(
        model=cfg["model"],
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _stream_anthropic(cfg: dict, messages: list, temperature: float, max_tokens: int):
    try:
        from anthropic import Anthropic
    except ImportError:
        raise ImportError("请安装 anthropic SDK: pip install anthropic")

    client = Anthropic(api_key=cfg["api_key"])

    system_text = ""
    chat_messages = []
    for m in messages:
        if m["role"] == "system":
            system_text = m["content"]
        else:
            chat_messages.append({"role": m["role"], "content": m["content"]})

    if not chat_messages:
        chat_messages = [{"role": "user", "content": "hello"}]

    kwargs = {
        "model": cfg["model"],
        "max_tokens": max_tokens,
        "messages": chat_messages,
        "temperature": temperature,
    }
    if system_text:
        kwargs["system"] = system_text

    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text


PLC_SYSTEM_PROMPT = """你是一名资深的西门子PLC工程师，精通TIA Portal V18/V19编程。

专业能力：
- 使用SCL、LAD、FBD、STL语言编写PLC程序
- 熟悉S7-1200/1500系列PLC
- 熟悉IEC 61131-3标准
- 熟悉工业自动化控制（电机控制、PID调节、顺序控制、通信等）

回答要求：
1. 代码必须符合TIA Portal语法规范
2. 包含完整的变量声明和注释
3. 遵循安全编程原则（互锁、急停、故障处理）
4. 使用匈牙利命名法（bStart、qMotor、rSpeed）
5. 如果需求不明确，请先提问澄清
6. 优先使用SCL语言，除非用户指定其他语言"""
