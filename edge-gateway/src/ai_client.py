"""
Edge Gateway AI 客户端 — DeepSeek API 封装
按任务复杂度分流：简单读写 vs 复杂决策/代码生成
"""

import logging

from openai import AsyncOpenAI
from mcp_common.config import env_config

_settings = env_config()
logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 30


class AIClient:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=_settings.deepseek_api_key,
            base_url=_settings.deepseek_base_url,
            timeout=_TIMEOUT_SECONDS,
            max_retries=_MAX_RETRIES,
        )

    async def chat(self, messages: list[dict], complex_task: bool = False,
                   max_tokens: int = 0) -> str:
        model = _settings.deepseek_model_complex if complex_task else _settings.deepseek_model_simple
        limit = max_tokens or (3000 if complex_task else 2000)
        resp = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1 if complex_task else 0.3,
            max_tokens=limit,
        )
        return resp.choices[0].message.content or ""

    async def analyze_data(self, tags: list[dict], context: str = "") -> str:
        """分析 PLC 数据，返回自然语言分析"""
        tags_text = "\n".join(f'- {t["tag"]}: {t.get("value", "N/A")}' for t in tags)
        prompt = f"""你是一个工业自动化专家。以下是 PLC 当前数据：

{tags_text}

{context}

请分析：
1. 数据是否正常？
2. 有无异常需关注？
3. 如有异常，建议采取什么措施？"""
        return await self.chat([{"role": "user", "content": prompt}], max_tokens=2000)

    async def decide_control(self, situation: str, available_tags: list[str]) -> str:
        """AI 决策：根据当前状态决定控制动作"""
        tags_text = "\n".join(f"- {t}" for t in available_tags)
        prompt = f"""你是工业控制 AI 决策器。只能操作以下标签：
{tags_text}

当前情况：{situation}

请输出 JSON 格式的控制决策：
{{"action": "write"|"wait"|"alert", "target": "标签名", "value": 目标值, "reason": "原因"}}

安全规则：
- 绝不操作急停、安全回路标签
- 值变化不超过当前值的 50%
- 不确定时返回 action: "alert"
"""
        return await self.chat([{"role": "user", "content": prompt}], complex_task=True)


ai = AIClient()
