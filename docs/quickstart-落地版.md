# AI-PLC 快速上手 (落地版)

5 步从零到运行第一个 AI 生成的 PLC 程序。

---

## 第 1 步：安装 TIA Portal + PLCSIM Advanced

### 需要安装的软件

| 软件 | 版本要求 | 说明 |
|------|---------|------|
| TIA Portal | V18 或 V21 | 包含 STEP 7 Professional |
| S7-PLCSIM Advanced | V5.0+ | PLC 仿真器 |
| TIA Openness | 与 TIA Portal 配套 | 自动化 API（TIA Portal 安装时可选组件） |

### 安装注意事项

1. **安装顺序**：先装 TIA Portal，再装 PLCSIM Advanced
2. TIA Portal 安装时勾选 "TIA Portal Openness" 组件
3. 安装到英文路径（避免中文路径导致的编码问题）
4. PLCSIM Advanced V5.0+ 需要 Win10/11 64 位 + Hyper-V 支持

![screenshot-placeholder: TIA Portal 安装界面 — 勾选 Openness 组件]

### 检查清单

- [ ] TIA Portal 可以正常打开项目
- [ ] PLCSIM Advanced 可以创建仿真实例
- [ ] `D:\TIA FANG ZHEN` 目录存在（或在 config.yaml 中配置的路径）

---

## 第 2 步：配置 DeepSeek API Key

### 方式 1：环境变量（推荐）

```bat
set DEEPSEEK_API_KEY=sk-your-api-key-here
```

或在系统环境变量中永久设置：
1. Win + R 打开 "sysdm.cpl"
2. 高级 -> 环境变量 -> 新建用户变量
3. 变量名：`DEEPSEEK_API_KEY`，变量值：你的 Key

### 方式 2：.env 文件

在项目根目录 (`AI 接入PLC/`) 创建 `.env` 文件：

```ini
DEEPSEEK_API_KEY=sk-your-api-key-here
```

### 获取 API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册账号并充值
3. 在 "API Keys" 页面创建 Key

### 检查清单

- [ ] `DEEPSEEK_API_KEY` 环境变量已设置
- [ ] 运行 `python scripts/preflight.py` 显示 "DeepSeek API Key: PASS"

---

## 第 3 步：打开 TIA Portal

### 必须以管理员权限运行

TIA Portal 中的自动化操作需要管理员权限。

1. 右键点击 TIA Portal 图标
2. 选择 "以管理员身份运行"
3. 打开或新建一个项目

> **重要**：TIA Portal 必须保持打开状态。所有编译、下载操作都通过 Openness API 与正在运行的 TIA Portal 交互。

### 配置项目路径

编辑 `mcp-servers/tia-mcp/config.yaml`，确认以下路径与实际匹配：

```yaml
tia:
  project_path: "D:\\PLC cheng xu\\TIA PLC CHENG XU\\demo\\demo.ap18"  # 你的项目路径
  install_dir: "D:\\TIA BEN TI\\Portal V18"  # TIA Portal 安装路径
  output_dir: "D:\\TIA FANG ZHEN"  # 输出目录
```

### 检查清单

- [ ] TIA Portal 以管理员权限打开
- [ ] 项目可以正常打开
- [ ] config.yaml 中的 project_path 指向正确路径
- [ ] PLCSIM Advanced 已安装

![screenshot-placeholder: TIA Portal 以管理员权限运行 — 项目视图]

---

## 第 4 步：运行 start.bat

### 启动所有服务

双击项目根目录下的 `start.bat`，将依次启动：

| 服务 | 端口/模式 | 功能 |
|------|----------|------|
| orchestrator | HTTP :8000 | 编排引擎，串联所有 MCP 工具 |
| backend | HTTP :8001 | Web 后端 API |
| plc-mcp-bridge | stdio MCP | S7 运行时读写 + 工程操作 |
| tia-mcp | stdio MCP | TIA Portal Openness API 调用 |
| robot-mcp | stdio MCP | Factory I/O 机器人控制 |

### 启动输出示例

```
============================================
  AI PLC Integration — 一键启动所有服务
============================================

[OK] Python: D:\Python3\python.exe
[OK] 前置检查通过

[1/5] 启动 orchestrator (端口 8000) ... [OK]
[2/5] 启动 backend (端口 8001) ... [OK]
[3/5] 启动 plc-mcp-bridge ... [OK]
[4/5] 启动 tia-mcp ... [OK]
[5/5] 启动 robot-mcp ... [OK]

============================================
  启动完成
============================================
```

### 常见问题

**Q: "Python 未找到"**
修改 `start.bat` 顶部 `PYTHON` 变量为你的 Python 路径。

**Q: "端口 8000 已被占用"**
检查是否有旧进程未关闭：
```bat
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Q: MCP 服务启动后立即退出**
检查各 MCP 服务器的依赖是否完整：
```bat
pip install -r requirements.txt
```

### 检查清单

- [ ] 5 个命令行窗口已打开，无错误输出
- [ ] orchestra 窗口显示 "Uvicorn running on http://127.0.0.1:8000"
- [ ] backend 窗口显示 "Uvicorn running on http://127.0.0.1:8001"

![screenshot-placeholder: 5 个命令行窗口 — orchestrator / backend / plc-mcp-bridge / tia-mcp / robot-mcp]

---

## 第 5 步：运行演示

### 运行一键演示脚本

```bat
python scripts/demo.py
```

演示脚本将：

1. 自动检查前置条件
2. 调用 orchestrator API，通过 AI 生成 "三相异步电机正反转带急停和过载保护" 的 SCL 代码
3. 自动编译并下载到 PLCSIM
4. 通过 snap7 读取 M0.0 验证 PLC 变量

### 预期输出

```
╔══════════════════════════════════════════════════════╗
║  AI-PLC 一键演示                                     ║
╚══════════════════════════════════════════════════════╝

固定 Prompt: 三相异步电机正反转带急停和过载保护
Orchestrator: http://127.0.0.1:8000

┌────────────────────────────────────────────────────┐
│ Step 1/4: 前置条件检查                              │
└────────────────────────────────────────────────────┘
[HH:MM:SS] OK    orchestrator 已就绪
[HH:MM:SS] OK    DeepSeek API Key 已配置
[HH:MM:SS] OK    Python 依赖完整
[HH:MM:SS] OK    前置检查完成

┌────────────────────────────────────────────────────┐
│ Step 2/4: 全流水线: 三相异步电机正反转带急停和过载保护│
└────────────────────────────────────────────────────┘
[HH:MM:SS] 项目: Demo_20260623_143022
[HH:MM:SS] OK    全流水线成功 (42.3s)
[HH:MM:SS] 共 6 个步骤:
    [1] PASS plc-mcp-bridge.plc_create_project (120ms)
    [2] PASS plc-mcp-bridge.plc_create_instance (340ms)
    [3] PASS tia-mcp.generate_scl_code (3500ms)
    [4] PASS tia-mcp.import_scl_file (800ms)
    [5] PASS plc-mcp-bridge.plc_compile_project (15000ms)
    [6] PASS plc-mcp-bridge.plc_download_project (22000ms)

┌────────────────────────────────────────────────────┐
│ Step 3/4: snap7 PLC 变量验证                        │
└────────────────────────────────────────────────────┘
[HH:MM:SS] OK    snap7 连接成功
[HH:MM:SS] OK    M0.0 = True (电机运行位)

┌────────────────────────────────────────────────────┐
│ Step 4/4: 演示总结                                  │
└────────────────────────────────────────────────────┘

  总耗时: 45.2s
  Prompt: 三相异步电机正反转带急停和过载保护

  ╔══════════════════════════════════════╗
  ║                                      ║
  ║     >>> Demo 运行成功 <<<            ║
  ║                                      ║
  ╚══════════════════════════════════════╝
```

### 快速冒烟测试

如果只需要验证核心链路（跳过前置检查的详细输出）：

```bat
python scripts/e2e_smoke.py
```

### 常见问题

**Q: "orchestrator 不可达"**
确认 `start.bat` 已运行，orchestrator 窗口无错误。

**Q: "SCL 生成失败"**
检查 DeepSeek API Key 是否有效、网络是否可访问 `api.deepseek.com`。

**Q: "编译失败"**
1. TIA Portal 是否以管理员权限打开？
2. 项目路径是否包含中文？（如 `D:\\PLC cheng xu`，当前版本可能不兼容）
3. 确认 TIA Openness API 组件已安装

**Q: "下载到 PLCSIM 失败"**
1. PLCSIM Advanced 实例是否已创建？
2. IP 地址是否与配置一致？（默认 192.168.0.1）
3. TIA 下载设备是否为 `S7-1500/ET200MP station_1`（CPU item `PLC_2`）？
4. 运行 `python scripts/preflight.py` 检查 PLCSIM 状态

**Q: "snap7 读取失败"**
1. 安装 python-snap7：`pip install python-snap7`
2. PLCSIM 下载完成后需要切换到 RUN 模式

### 检查清单

- [ ] `demo.py` 所有 4 步均显示 PASS
- [ ] 大字 "Demo 运行成功" 出现在最终输出
- [ ] TIA Portal 中可以看到生成的 SCL 代码块

![screenshot-placeholder: demo.py 运行完成 — 大字 "Demo 运行成功"]

---

## 快速参考

| 命令 | 用途 |
|------|------|
| `start.bat` | 一键启动所有 5 个服务 |
| `python scripts/preflight.py` | 前置条件检查 |
| `python scripts/e2e_smoke.py` | 端到端冒烟测试 |
| `python scripts/demo.py` | 一键演示（带进度条和大字结果） |
| `python scripts/preflight.py --json` | JSON 格式前置检查输出 |

## 项目链接

- 项目文档：[docs/project-overview.md](project-overview.md)
- 环境配置：[docs/environment.md](environment.md)
- 架构设计：`.plans/ai-plc-integration/`
