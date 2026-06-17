"""生成工作流 — 自然语言 → LLM → 结构化梯形图输出"""

from typing import Optional

from generator import LadderProgram, build_demo_program, parse_raw_output
from llm.service import chat


LADDER_GENERATION_PROMPT = """你是一名西门子PLC工程师，使用TIA Portal V18编程。

请根据以下需求生成梯形图（LAD）程序：

需求：{user_input}

{context_info}

请严格按照以下格式输出：

# 程序标题

> 程序说明

## 变量表
| 地址 | 符号 | 类型 | 注释 |
|------|------|------|------|
| I0.0 | bExample | Bool | 示例 |

## Network 1: 网络标题
// 注释说明
```
梯形图代码（使用ASCII符号: --| |-- 常开触点, --|/|-- 常闭触点, --( )-- 线圈）
```

## Network 2: 网络标题
// 注释说明
```
梯形图代码
```

确保：
1. 变量命名使用匈牙利命名法（bStart、qMotor、rSpeed）
2. 每个 Network 都有清晰注释
3. 包含安全互锁逻辑（急停、过载保护）
4. 地址从 I0.0、Q0.0、M0.0 开始合理分配
5. 梯形图使用ASCII符号绘制"""


def generate_ladder(
    user_input: str,
    template_id: Optional[str] = None,
    variables: Optional[dict] = None,
    context: Optional[dict] = None,
    model_id: str = "deepseek",
) -> dict:
    """自然语言 → 梯形图程序

    优先调用 LLM 生成，失败时回退到内置 demo。
    """
    # 尝试 LLM 生成
    try:
        prompt = build_prompt(user_input, context)
        raw = chat(model_id=model_id, messages=[{"role": "user", "content": prompt}], temperature=0.3, max_tokens=8192)
        program = parse_raw_output(raw)

        # 如果解析出有效内容则使用 LLM 结果
        if program.networks:
            return {
                "title": program.title or user_input[:50],
                "description": program.description or "",
                "input": user_input,
                "text": program.to_text(),
                "structured": program.to_dict(),
                "mode": "llm",
            }
    except Exception:
        pass  # LLM 调用或解析失败，回退 demo

    # 回退：内置 demo
    demo_keywords = {
        "电机": "motor-start-stop",
        "启动": "motor-start-stop",
        "停止": "motor-start-stop",
        "交通灯": "traffic-light",
        "红绿灯": "traffic-light",
        "传送带": "conveyor",
        "输送带": "conveyor",
    }

    matched = template_id
    if not matched:
        for kw, demo_id in demo_keywords.items():
            if kw in user_input:
                matched = demo_id
                break

    if matched and matched in ("motor-start-stop", "traffic-light", "conveyor"):
        program = build_demo_program(matched, variables or {})
        mode = "demo"
    else:
        program = LadderProgram(user_input[:50], f"根据描述生成: {user_input[:100]}")
        program.add_variable("I0.0", "bInput1", "Bool", "输入信号1")
        program.add_variable("Q0.0", "qOutput1", "Bool", "输出信号1")
        program.add_network(1, "主逻辑",
            "     bInput1          qOutput1\n------| |--------------( )--",
            "LLM 不可用，请检查 API Key 配置")
        mode = "placeholder"

    return {
        "title": program.title,
        "description": program.description,
        "input": user_input,
        "text": program.to_text(),
        "structured": program.to_dict(),
        "mode": mode,
    }


def build_prompt(user_input: str, context: Optional[dict] = None) -> str:
    """构建 LLM Prompt"""
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

    return LADDER_GENERATION_PROMPT.format(
        user_input=user_input,
        context_info=context_info,
    )
