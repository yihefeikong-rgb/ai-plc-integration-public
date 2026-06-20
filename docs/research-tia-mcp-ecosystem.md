# TIA Portal MCP 生态研究报告

> 生成: 2026-06-16 | 最后更新: 2026-06-16 | 来源: 15+ 项目源码 + 西门子官方文档 + 社区讨论
>
> **⚠️ 过期声明**：本报告中提及的 TiaCommander 闭源 beta 已于 2026-06-19 到期，不可用。本项目已采用自研 TiaWorker (C#) 替代方案。

## 一、生态全景

### 1.1 所有已知项目对比

| 项目 | Stars | 许可证 | 工具数 | 架构 | TIA 版本 | 特点 |
|------|:-----:|:------:|:------:|:----:|:---------|:-----|
| [heilingbrunner/tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp) | ⭐64 | MIT | ~30 | 单进程 .NET 4.8 | V18-V20 | **最火开源**，VS Code 扩展 |
| [bulaofen0036-coder/TIA_Portal_Openness_MCP](https://github.com/bulaofen0036-coder/TIA_Portal_Openness_MCP) | ⭐45 | MIT | ~50+ | 单进程 .NET 4.8 | V20+V21 | **开发最活跃**，15个release，双版本 |
| [Czarnak/totally-integrated-claude](https://github.com/czarnak/totally-integrated-claude) | ⭐26 | MIT | Plugin | 多Agent | V21 | Claude Code 插件 + LSP |
| [StaniB88/TIAOpennessManager](https://github.com/StaniB88/TIAOpennessManager) | ⭐33 | 专有 | 产品 | 桌面应用 | V15-V21 | 功能最全的桌面工具，有AI Chat |
| [chewcw/tia-portal-openness-mcpserver](https://github.com/chewcw/tia-portal-openness-mcpserver) | ⭐22 | MIT | ~20 | 单进程 .NET 4.8 | V20 | 有单元测试，CLI工具 |
| [a4webdev/tiacommander-mcp](https://github.com/a4webdev/tiacommander-mcp) | ⭐12 | 专有(beta) | **166** | 单进程 .NET 4.8 | V15.1-V21 | **最成熟商业**，16 tools 166 actions (v2.26.3) |
| [Czarnak/tia-portal-mcp](https://github.com/Czarnak/tia-portal-mcp) | ⭐9 | MIT | ~15 | **双进程** .NET 8+4.8 | V21 | 双进程架构，safetyToken |
| **我们 (TiaWorker)** | — | MIT | **55** | 子进程JSON | V18 | 已含S7+Safety+AI闭环 |

### 1.2 商业产品

| 产品 | 工具数 | 价格 | 特点 |
|------|:------:|:----:|:------|
| **TiaCommander** | 166 actions | beta免费→收费 | 16 tools，166 actions，v2.26.3 |
| **T-IA Connect** | **393 tools** | 商业收费 | 功能最全面，含HMI/PLCSim/版本控制 |
| **TIA Openness Manager** | 桌面应用 | 商业收费 | AI Chat + OPC UA + 版本控制 |

### 1.3 开源项目功能矩阵

| 功能 | TiaCommander | T-IA Connect | 开源平均 | **我们** |
|:----|:------------:|:------------:|:--------:|:--------:|
| 项目管理(创建/打开/保存/归档) | ✅ 15 | ✅ 19 | ✅ | ✅ 6 |
| 块管理(增删改查) | ✅ 29 | ✅ 23 | ✅ | ✅ 11 |
| DB 操作 | ✅ 9 | ✅ | ✅ | ✅ 3 |
| 标签表管理 | ✅ 12 | ✅ 33 | ✅ | ✅ 7 |
| UDT 管理 | ✅ 10 | ✅ | ✅ | ✅ 4 |
| 监控表 | ✅ 13 | ✅ 11 | ✅ | ✅ 3 |
| **硬件配置** | ✅ 12 | ✅ 12 | ⚠️ 部分 | ❌ |
| **库管理** | ✅ 26 | ✅ 20 | ❌ | ❌ |
| **HMI/WinCC** | ❌(计划中) | ✅ 51 | ⚠️ 部分 | ❌ |
| **报警文本** | ✅ 15 | ✅ 13 | ❌ | ❌ |
| **诊断/在线** | ✅ 6 | ✅ 10 | ❌ | ❌ |
| **安全功能** | ⚠️ 有限 | ✅ 8 | ❌ | ❌ |
| **版本控制** | ❌ | ✅ 17 | ❌ | ❌ |
| **PLCSIM 仿真** | ❌(计划中) | ✅ 35 | ⚠️ 部分 | ✅ 7 |
| S7 运行时通信 | ❌(计划中) | — | ❌ | ✅ |
| AI 控制闭环 | ❌ | — | ❌ | ✅ |
| Safety 安全模块 | ❌ | — | ❌ | ✅ |

---

## 二、关键技术发现

### 2.1 架构共识

**所有项目都使用同一模式**：.NET Framework 4.8 + TIA Openness API，通过 stdio JSON-RPC 通信。

三种实现方式：
1. **单进程 .NET 4.8**（heilingbrunner, bulaofen, TiaCommander）— 最简单，直接引用 Siemens.Engineering.dll
2. **双进程 .NET 8 + .NET 4.8 worker**（Czarnak）— 解耦MCP协议层和Openness，worker进程隔离
3. **Python MCP + .NET CLI**（controlbyte.tech 指南, **我们的架构**）— Python 处理 MCP，子进程调 .NET CLI

**我们的架构和 controlbyte.tech 的推荐方案完全一致**，这是好的验证。

### 2.2 V21 重大变更

**V21 将单体的 `Siemens.Engineering.dll` 拆分为模块化 DLL：**

```
C:\Program Files\Siemens\Automation\Portal V21\PublicAPI\V21\net48\
  Siemens.Engineering.Base.dll     — TiaPortal, Project, HW, Compiler
  Siemens.Engineering.Step7.dll    — PlcSoftware, Blocks, Tags, Types
  Siemens.Engineering.WinCC.dll    — HMI Classic
  Siemens.Engineering.WinCCUnified.dll
  Siemens.Engineering.Safety.dll
  ...
```

关键影响：
- V20 和 V21 的 DLL **完全不兼容**，需要各自独立编译
- V21 需要 `AssemblyResolve` 事件处理器动态加载 DLL
- V21 public key token 变了，使用 `SpecificVersion=false` 解决
- V21 不再支持 V17/V18/V19/V20 的应用

### 2.3 COM STA 线程模型

**Openness API 使用 COM 对象，要求 Single-Threaded Apartment (STA) 模式：**

- .NET Framework 4.8 的 WinForms 应用默认主线程是 STA ✅
- 控制台应用默认是 MTA ❌（需要 `[STAThread]` 或手动 StaDispatcher）
- .NET 6/8 不支持 .NET Remoting，无法直接加载 Openness DLL
- T-IA Connect 对比页指出：多数开源实现"works by luck on STA"，但并发时会出问题

**我们的 TiaWorker 是 WinForms exe，默认 STA，没问题。**

### 2.4 Openness API 已知限制

- **在线诊断数据不可编程获取**（固件版本、序列号等）
- **首次 PG/PC 连接必须在 TIA Portal GUI 中配置**
- **网络扫描需要已打开的项目**
- **不能直接通过 DCP 分配 IP 地址**，必须修改项目硬件配置再下载
- **Failsafe 块有额外限制**
- **HMI 编辑器在无 UI 模式下不可用**

---

## 三、对我们的改进建议

### 优先级 P0（必须做）

1. **JSON 响应格式规范化**
   - 统一为 `{"ok": true/false, "result": {}, "error": ""}`
   - 当前不一致：有的返回 `{success, data, error}`，有的直接放字符串

2. **版本兼容性支持**
   - 编译 V18 版本（已有）
   - 增加 `--tia-major-version` 启动参数

### 优先级 P1（应该做）

3. **V21 支持**
   - 创建 V21 独立构建
   - 引用 `Siemens.Engineering.Base.dll` + `Step7.dll` 替代单体
   - AssemblyResolve 动态加载

4. **Dry-Run 模式**
   - 所有写入操作默认 dry-run=true
   - 调用者显式传入 confirm=true 才执行

5. **错误处理增强**
   - 子进程超时重试
   - 统一的错误码和中文错误描述
   - TIA Portal 连接瞬态失败自动重试

### 优先级 P2（丰富功能）

6. **硬件配置工具**（12 tools）
   - 读取设备配置（rack/slot 拓扑）
   - 硬件 I/O 映射导出
   - 网络配置（IP/子网）

7. **库管理**（26 tools）
   - 全局库和项目库操作
   - Master Copy 发布和实例化

8. **诊断工具**（6 tools）
   - PLC 运行状态读取
   - Online/Offline 切换
   - 项目与 PLC 对比

### 优先级 P3（锦上添花）

9. **preview-then-apply 安全模式**（参考 Czarnak 的 safetyToken）
10. **项目修改前自动备份**
11. **CSV/XLSX 导出标签表/监控表**
12. **标签冲突检测和空闲地址查询**

---

## 四、需要进一步研究的

1. **HMI/WinCC Unified** — T-IA Connect 有 51 tools，西门子 V21 支持 WinCC Unified 的 Openness API，但我们的 TIA Portal V18 可能不支持
2. **V21 模块化 DLL 迁移** — 需要实际安装 V21 测试
3. **双进程架构** — 目前单进程已够用，除非迁移到 .NET 8

---

## 五、来源

1. [heilingbrunner/tiaportal-mcp](https://github.com/heilingbrunner/tiaportal-mcp) — 64⭐，最火MCP开源实现
2. [bulaofen0036/TIA_Portal_Openness_MCP](https://github.com/bulaofen0036-coder/TIA_Portal_Openness_MCP) — 39⭐，MIT，V20+V21双版本
3. [Czarnak/tia-portal-mcp](https://github.com/Czarnak/tia-portal-mcp) — 双进程架构 + safetyToken
4. [Czarnak/totally-integrated-claude](https://github.com/czarnak/totally-integrated-claude) — 26⭐，Claude插件+LSP
5. [a4webdev/tiacommander-mcp](https://github.com/a4webdev/tiacommander-mcp) — 166 actions，商业beta
6. [T-IA Connect](https://t-ia-connect.com/en/mcp-server-tia-portal) — 393 tools，商业产品
7. [controlbyte.tech 实操指南](https://controlbyte.tech/blog/tia-portal-mcp-server-ai-automation/) — Python MCP + .NET CLI 架构
8. [T-IA Connect 对比页](https://t-ia-connect.com/en/mcp-tia-portal-comparison) — 各开源项目的架构缺陷分析
9. [西门子 Openness V21 官方文档](https://docs.tia.siemens.cloud/r/en-us/v21/readme-tia-portal-openness/major-changes-for-long-term-stability-in-tia-portal-openness-v21)
10. [TIA Portal Openness 兼容性矩阵](https://t-ia-connect.com/en/compatibility-tia-portal-openness)
11. [NuGet: Siemens.Openness.Resolver](https://www.nuget.org/packages/Siemens.Collaboration.Net.TiaPortal.Openness.Resolver) — V21 程序集解析库
