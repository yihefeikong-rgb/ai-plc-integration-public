"""生成工作流 — 自然语言 → LLM → ASCII-LAD-V2 → LadderModel"""

import re
from typing import Optional

from generator.ascii_parser import parse_ascii_lad
from generator.ladder_model import program_to_dict
from llm.service import chat


class GenerationError(RuntimeError):
    """模型或解析失败时，禁止返回可被误当作真实程序的替代样例。"""


# ═══════════════════════════════════════════════════════════
# ASCII-LAD-V2 Prompt
# ═══════════════════════════════════════════════════════════

LADDER_V2_PROMPT = """你是西门子PLC工程师（TIA Portal V18）。根据需求生成梯形图程序。

**严格使用 ASCII-LAD-V2 格式输出。** 不要输出其他格式或额外说明。

格式规范：

```
ASCII-LAD-V2

Variables:
<地址>    <符号名>    <数据类型>    <中文注释>

Network <编号>
Title: <标题>

Comment:
<功能说明>

|----<元素>----<元素>----...----<元素>
```

元素语法：
- 常开触点: [ 符号名 ]
- 常闭触点: [/ 符号名 ]
- 线圈: ( 符号名 )
- 置位线圈: (S 符号名)
- 复位线圈: (R 符号名)
- 接通延时: [TON 名称 PT=时间]
- 断开延时: [TOF 名称 PT=时间]
- 脉冲: [TP 名称 PT=时间]
- 加计数: [CTU 名称 PV=预设值]
- 减计数: [CTD 名称 PV=预设值]
- 赋值: [MOVE IN=源 OUT=目标]
- 比较: [CMP 操作 A B]（操作: EQ/NE/GT/GE/LT/LE）
- TON/CTU的Q输出隐含在梯级流中，跨Network引用时需声明映射变量

并联(OR逻辑)用 Branch — 两个 + 必须垂直对齐：
|----[ A ]----+----( Out )
|             |
|----[ B ]----+

规则：
1. 匈牙利命名法（bStart, qMotor, rSpeed）
2. 包含安全互锁（急停、过载保护）
3. 地址从 I0.0, Q0.0, M0.0 开始分配
4. Branch 仅限单层（不嵌套）
5. 只输出 ASCII-LAD-V2 格式，不要其他内容

完整示例：

ASCII-LAD-V2

Variables:
I0.0    bStart     BOOL    启动按钮
I0.1    bStop      BOOL    停止按钮
I0.2    bOL        BOOL    过载保护
Q0.0    qMotor     BOOL    电机输出

Network 1
Title: 电机启动自锁

Comment:
按下启动按钮后电机运行并自锁
按下停止或过载时停止

|----[ bStart ]----[/ bStop ]----[/ bOL ]----+----( qMotor )
|                                            |
|----[ qMotor ]------------------------------+

需求：{user_input}
{context_info}"""


# ═══════════════════════════════════════════════════════════
# LLM 输出提取
# ═══════════════════════════════════════════════════════════

def _extract_ascii_lad(raw: str) -> str:
    """从 LLM 输出中提取 ASCII-LAD-V2 内容。

    处理：
    1. 直接输出（无 code fence）
    2. 被 ```...``` 包裹
    3. 前后有额外说明文字
    """
    # 先尝试从代码块中提取
    fence_match = re.search(
        r'```(?:\w*)\s*\n?(ASCII-LAD-V2.*?)```',
        raw,
        re.DOTALL,
    )
    if fence_match:
        return fence_match.group(1).strip()

    # 直接查找 ASCII-LAD-V2 标记
    idx = raw.find('ASCII-LAD-V2')
    if idx >= 0:
        return raw[idx:].strip()

    # 最后手段：返回原文
    return raw.strip()


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def generate_ladder(
    user_input: str,
    template_id: Optional[str] = None,
    variables: Optional[dict] = None,
    context: Optional[dict] = None,
    model_id: str = "deepseek",
) -> dict:
    """自然语言 → 梯形图程序

    流程：LLM → ASCII-LAD-V2 文本 → ascii_parser → LadderModel → dict
    任一环节失败即明确失败，绝不自动返回可导出/导入的演示程序。
    """
    try:
        prompt = build_prompt(user_input, context)
        raw = chat(model_id=model_id, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=4096)
        ascii_text = _extract_ascii_lad(raw)
        program = parse_ascii_lad(ascii_text)
        if not program.networks:
            raise GenerationError("模型输出未包含可验证的梯形图网络")
        structured = program_to_dict(program)
        return {
            "title": structured.get("title") or user_input[:50],
            "description": structured.get("description", ""),
            "input": user_input,
            "text": ascii_text,
            "structured": structured,
            "mode": "llm",
        }
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError("模型生成或梯形图解析失败") from exc


def build_prompt(user_input: str, context: Optional[dict] = None) -> str:
    """构建 ASCII-LAD-V2 生成 Prompt"""
    context_info = ""
    if context:
        parts = []
        if context.get("project"):
            parts.append(f"当前项目：{context['project']}")
        if context.get("plc_type"):
            parts.append(f"PLC类型：{context['plc_type']}")
        if context.get("io_table"):
            parts.append(f"\nIO表：\n{context['io_table']}")
        context_info = "\n".join(parts)

    return LADDER_V2_PROMPT.format(
        user_input=user_input,
        context_info=context_info,
    )
