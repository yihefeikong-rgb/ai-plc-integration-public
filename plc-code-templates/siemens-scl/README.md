# 西门子 SCL 代码模板库

AI 生成 PLC 代码时的 Prompt 模板，每个模板含完整 SCL 代码示例 + 命名规范 + 安全规则。

## 模板列表

| 文件 | 场景 | 复杂度 |
|------|------|:------:|
| `motor-control.md` | 电机正反转 + 急停 + 过载 + 限位 | ⭐⭐ |
| `conveyor.md` | 多段传送带 + 堵料检测 + 满料停止 | ⭐⭐ |
| `pid-controller.md` | PID 控制器 + 积分分离 + 抗饱和 | ⭐⭐⭐ |

## 引用的提示模板（在 server.py 的 _LAD_PROMPT_TEMPLATE 中）

用于 `generated_scl_code` 和 `generate_and_import` 工具的 template 参数：
- `motor` → motor-control.md
- `conveyor` → conveyor.md  
- `pid` → pid-controller.md
- `general` → 通用（不含模板）

## LAD 模板（在 mcp-servers/tia-mcp/templates/ 中）

用于 `create_ladder_block` 工具的 21 个 LAD 模板：
见 `mcp-servers/tia-mcp/templates/` 目录

## 安全规则（所有模板通用）
1. 急停互锁（NOT iEStop → 无条件停止）
2. 过载/过流保护
3. 正反转互锁
4. 输出限幅（模拟量）
5. 故障状态机（0=STOP, 1=RUN, 3=FAULT）
6. 匈牙利命名法（bBool, rReal, iInt, tonTimer）
