"""
DeepSeek API 调用封装 — 从 tia-mcp/server.py 抽取。

消除 _gen_scl_via_deepseek() 和 _call_deepseek() 的代码重复。

用法:
    from mcp_common.deepseek import call_deepseek, parse_json_response

    response = call_deepseek(prompt, api_key="sk-xxx", model="deepseek-chat")
    data = parse_json_response(response)  # 从 AI 输出中提取 JSON
"""

import json
import re
import requests
from typing import Optional


def call_deepseek(
    prompt: str,
    api_key: str = "",
    api_url: str = "https://api.deepseek.com/v1/chat/completions",
    model: str = "deepseek-chat",
    temperature: float = 0.3,
    max_tokens: int = 4000,
    timeout: int = 120,
) -> dict:
    """调用 DeepSeek API，返回完整响应 JSON。

    Args:
        prompt: 用户提示词
        api_key: DeepSeek API Key（留空从环境变量 DEEPSEEK_API_KEY 读取）
        api_url: API 端点
        model: 模型名称
        temperature: 生成温度
        max_tokens: 最大 token 数
        timeout: 超时秒数

    Returns:
        API 响应的完整 JSON dict

    Raises:
        ValueError: API Key 未配置
        requests.RequestException: 网络错误
    """
    if not api_key:
        import os
        api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("未配置 DEEPSEEK_API_KEY（请在 .env 或环境变量中设置）")

    resp = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def parse_json_response(response: dict) -> dict:
    """从 DeepSeek 响应 content 中提取 JSON。

    支持多种格式:
      - ```json ... ```
      - ``` ... ```
      - 直接 JSON 文本

    Returns:
        解析后的 dict

    Raises:
        ValueError: 无法提取 JSON
        json.JSONDecodeError: JSON 解析失败
    """
    content = response["choices"][0]["message"]["content"]

    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if json_match:
        raw = json_match.group(1).strip()
    else:
        raw = content.strip()

    return json.loads(raw)
