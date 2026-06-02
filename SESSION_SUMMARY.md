## 项目位置
D:\claude code xiangmu\AI 接入PLC\

## 当前阶段：阶段 2 → 阶段 3 过渡中

---

## 已完成（本次会话）

### 多 AI 问答获取 PLCSIM 备份方案
咨询了 6 个 AI（Kimi / ChatGPT / Gemini / 腾讯元宝 / 豆包 / 智谱清言），确认：
- **核心 API**: `ArchiveStorage/RetrieveStorage`（不是 Backup/Restore）
- 将虚拟 SIMATIC 存储卡（含硬件配置+程序）打包成 ZIP
- 必须在 OFF 状态调用

### PLCSIM 首次下载障碍突破

| 步骤 | 状态 |
|------|:--:|
| TIA Portal GUI 手动下载到 factory io1（最后一次） | ✅ |
| `ArchiveStorage` → golden.zip（146 KB） | ✅ |
| `plcsim_api.py` 完善中 | 🟡 |
| TCP/IP 切换待解决 | ⏳ |

**关键经验**：`StoragePath` 必须在 TIA Portal 下载前设置，否则 PowerOff 后内容丢失。

### 全自动化流程（后续）
```python
RegisterInstance → StoragePath → RetrieveStorage(golden.zip) 
→ SetCommunicationInterface(TCPIP) → SetIPSuite → PowerOn → Run()
```

### 新建/修改的文件
- **`mcp-servers/tia-mcp/plcsim_api.py`** — 350 行，PLCSIM Advanced .NET API 完整封装
- **`mcp-servers/tia-mcp/check_status.py`** — 实例状态检查
- **`mcp-servers/tia-mcp/create_golden*.py`** — 黄金备份创建脚本
- **`mcp-servers/tia-mcp/switch_to_tcpip.py`** — TCP/IP 切换（遇到 VirtualSwitchMisconfigured）
- **`mcp-servers/tia-mcp/*.py`** — 各类测试脚本

### PLCSIM 当前状态
- factory io1: **Softbus RUN**
- 黄金备份: `D:\PLC cheng xu\TIA PLC CHENG XU\demo\factory_io1_golden.zip`

---

## 下一步
1. 验证 `RetrieveStorage` 恢复流程
2. 解决 TCP/IP 虚拟网卡配置
3. 编写 Factory I/O auto.cfg
4. 三端一键启动脚本
