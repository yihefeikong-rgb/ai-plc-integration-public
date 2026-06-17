"""Mock LLM — 所有测试使用, 禁止真实调用模型"""

MOCK_CHAT_RESPONSE = """# 电机启动/停止控制

> 使用自锁电路实现电机启动和停止

## 变量表
| 地址 | 符号 | 类型 | 注释 |
|------|------|------|------|
| I0.0 | bStart | Bool | 启动按钮 |
| I0.1 | bStop | Bool | 停止按钮 |
| Q0.0 | qMotor | Bool | 电机输出 |

## Network 1: 启动保持
// 按下启动后自锁, 按停止断开
```
     bStart         bStop         qMotor
------| |----+-------|/|----------( )--
             |
             | qMotor
             +---| |
```

## Network 2: 故障指示
// 过载指示
```
     bOverload        qAlarm
------| |--------------( )--
```
"""

MOCK_SIMPLE_RESPONSE = "你好，我是 AI PLC 助手。"


def mock_chat(model_id="deepseek", messages=None, temperature=0.3, max_tokens=4096):
    """替代 llm.service.chat"""
    return MOCK_CHAT_RESPONSE


def mock_chat_with_fallback(model_id="deepseek", messages=None, temperature=0.3, max_tokens=4096):
    """替代 llm.service.chat_with_fallback"""
    return {
        "content": MOCK_CHAT_RESPONSE,
        "model": model_id,
        "fallback": False,
    }


def mock_chat_stream(model_id="deepseek", messages=None, temperature=0.3, max_tokens=4096):
    """替代 llm.service.chat_stream — 逐词 yield"""
    for word in MOCK_SIMPLE_RESPONSE.split():
        yield word + " "
