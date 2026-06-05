# 三菱 MC 协议 MCP Server

> 通过 MCP (Model Context Protocol) 让 AI 自然语言读写三菱 FX3U/FX5U/Q 系列 PLC。

---

## 使用方式

### 前置条件

| 需求 | 说明 |
|------|------|
| 三菱 PLC | FX3U / FX5U / Q 系列（或仿真器） |
| 网络连接 | PLC 通过以太网连接，开放 MC 协议端口 |
| .env 配置 | `MELSEC_HOST` + `MELSEC_PORT` |

### 环境变量

```bash
# .env
MELSEC_HOST=192.168.1.20   # 三菱 PLC IP
MELSEC_PORT=5001           # MC 协议端口（默认 5001）
```

### 启动

```bash
cd mcp-servers/mitsubishi-mcp
python server.py
# 暴露 3 个 MCP 工具：
#   read_device     — 读取单个设备
#   read_devices    — 批量读取
#   write_device    — 写入（带安全校验）
```

### MCP 工具

| 工具 | 参数 | 功能 |
|------|------|------|
| `read_device` | `addr: str` | 读取单个地址（如 `D100`, `M0`, `X10`） |
| `read_devices` | `addresses: list[str]` | 批量读取 |
| `write_device` | `addr: str`, `value: int`, `operator: str` | 写入（走 safety.validator 校验） |

---

## 支持的设备类型

| 类型 | 格式示例 | 位/字 | 说明 |
|:----|:---------|:-----:|:-----|
| M | `M100` | 位 | 中间继电器 |
| X | `X10` | 位 | 输入 |
| Y | `Y20` | 位 | 输出 |
| L | `L50` | 位 | 锁存继电器 |
| B | `B100` | 位 | 链接继电器 |
| T | `T5` | 位 | 定时器触点 |
| C | `C10` | 位 | 计数器触点 |
| S | `S0` | 位 | 步进继电器 |
| D | `D200` | 字 | 数据寄存器 |
| W | `W100` | 字 | 链接寄存器 |
| TN | `TN5` | 字 | 定时器当前值 |
| CN | `CN10` | 字 | 计数器当前值 |

---

## MC 协议说明

使用 **Binary 模式（4E 帧）** 通过 TCP 传输。

**请求帧结构：**
```
SUB_HEADER(2) + PC_NO(1) + MONITOR_TIMER(2) + DATA_LEN(2) + CMD(2) + SUB_CMD(2) + BODY
  - SUB_HEADER:    50 00 (请求)
  - PC_NO:         FF
  - MONITOR_TIMER: 10 00 (10 × 250ms = 2500ms 超时)
  - BODY:          设备码(1) + 地址(3) + 点数(2) + 数据/子命令
```

**响应帧结构（当前实现解析的格式）：**
```
SUB_HEADER(2) + ??(2) + END_CODE(2) + DATA
  - SUB_HEADER:  D0 00 (响应)
  - END_CODE:    00 00 = 成功
  - DATA:        读取的值（字: 每值 2 字节 LE / 位: 每 nibble 一个）
```

---

## 测试

```bash
# 协议层单元测试（不需要硬件）
python -m pytest mcp-servers/mitsubishi-mcp/test_mc_protocol.py -v

# 全量测试
python -m pytest tests/ mcp-servers/mitsubishi-mcp/ mcp-servers/tia-mcp/test_cartgen.py -v
```

测试覆盖：
- 设备地址解析（所有支持的设备类型）
- 帧结构验证（头部、命令码、body 长度匹配）
- 写入帧中值的偏移位验证
- 响应解析（字/位、空数据、错误码）
- 边界情况（最大地址、零值、负值编码）
- 往返一致性（构建→解析→验证）

---

## 安全

- 写入操作走 `safety.validator` 校验（急停禁用、熔断、值跳变检测）
- 所有操作记录到链式哈希审计日志 `safety.audit`
