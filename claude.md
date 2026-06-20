# AI 接入 PLC — 项目指令

> **项目目标**：构建 AI Agent 系统 + 本地工业自动化 AI 工作台，让 AI 通过自然语言监控、控制西门子 PLC，并自动生成 PLC 代码。
>
> **技术栈**：MCP + Python + C#/.NET + Electron + React + FastAPI + Docker + S7协议 + TIA Portal Openness

---

## 当前进度（2026-06-20）

| 模块 | 状态 |
|------|------|
| Phase 1: S7 运行态读写 | ✅ 完成 |
| Phase 2: AI 控制闭环 + 安全链 | ✅ 完成 |
| Phase 3: TIA 工程态 (TiaWorker) | ✅ 90% |
| AI PLC Assistant 桌面应用 V1.0 | ✅ 完成 |
| Phase 4: 工业机器人 | 未开始 |
| Phase 5: 统一编排 | 未开始 |
| 全仓审查修复 (63 A级) | ✅ 完成（58/58，2026-06-20） |
| 测试覆盖 | ✅ 174 pass / 0 fail |

---

## 项目结构

```
ai-plc-integration/
├── ai-plc-assistant/          # ⭐ 桌面 AI 工作台（Electron+React+FastAPI）
│   ├── frontend/              # React + TailwindCSS + Lucide
│   ├── backend/               # FastAPI + ChromaDB + SQLite
│   ├── start.bat              # 一键启动
│   └── README.md
├── mcp-servers/               # MCP 服务器集合
│   ├── plc-mcp-bridge/        # S7 协议 + TIA 工程操作（65 工具）
│   ├── tia-mcp/               # TIA Portal Openness（TiaWorker C#）
│   ├── opcua-mcp/             # OPC UA（备用）
│   ├── modbus-mcp/            # Modbus（骨架）
│   └── mitsubishi-mcp/        # 三菱 MC 协议（骨架）
├── edge-gateway/              # 边缘网关（S7+Modbus 双协议采集）
├── safety/                    # 安全模块（互锁/影子仿真/审计/熔断）
├── plc-code-templates/        # PLC 代码模板
├── tests/                     # 测试套件
├── scripts/                   # 运维脚本
└── docs/                      # 阶段文档
```

---

## 核心原则

### 安全优先
- 所有写入操作经互锁检查 + 影子仿真验证
- 审计日志全覆盖（链式哈希）
- 连续异常自动熔断
- 禁止 AI 操作急停回路

### 开发环境
- OS: Windows 11
- Python: `D:\Python3\python.exe` (3.13.2)
- TIA Portal: V21
- PLCSIM: Advanced V8.0 (TCP/IP Single Adapter)
- PLC IP: 192.168.0.110 (Rack=0, Slot=1)

### AI PLC Assistant 配置
- 后端端口: 8005
- DeepSeek API 已配置
- 模型支持: DeepSeek / OpenAI / Kimi / Claude / 自定义
- 启动: `ai-plc-assistant/start.bat`

---

## 安全红线

### 运行安全
1. **禁止 AI 直接操作急停回路**
2. **禁止 AI 修改安全 PLC（F-CPU）参数**
3. **所有控制指令必须经过影子仿真**
4. **生产环境写入需双人确认**（操作人 + 确认人不是同一人）
5. **审计日志不可篡改**（HMAC 链式哈希）

### 配置安全
6. **安装 global git hooks 前必须显示预览并确认**（列出要安装的 hook 内容，获得用户明确同意）
7. **修改 ~/.claude/settings.json 前必须先备份并显示 diff 预览**（备份路径: ~/.claude/settings.json.bak）
