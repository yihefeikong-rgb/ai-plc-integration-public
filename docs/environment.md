# 开发环境配置

## 系统环境
- OS: Windows 11
- Python: `D:\Python3\python.exe` (3.13.2)

## TIA Portal
- 版本: V21
- PLCSIM: Advanced V8.0 (TCP/IP Single Adapter)
- PLC IP: 192.168.0.1 (Rack=0, Slot=1)
- TIA 下载设备: `S7-1500/ET200MP station_1`（CPU item `PLC_2`）

## AI PLC Assistant
- 后端端口: 8005
- 前端: Electron + React (Vite) + TailwindCSS + Lucide
- 数据库: SQLite + ChromaDB
- 模型支持: DeepSeek / OpenAI / Kimi / Claude / 自定义
- 启动: `ai-plc-assistant/start.bat`

## 模型映射

| 角色 | 模型 |
|------|------|
| Team Lead（主对话） | DS-V4-Pro |
| Developer | DS-V4-Pro |
| Reviewer | Qwen3.7-Max |

## 测试

```bash
# Python 测试
D:/Python3/python.exe -m pytest tests/

# C# 测试
dotnet test mcp-servers/tia-mcp/TiaWorker/TiaWorker.Tests/
```
