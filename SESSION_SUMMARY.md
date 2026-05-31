## 项目位置
D:\claude code xiangmu\AI 接入PLC\

## 当前阶段：阶段 2 已完成，阶段 3 待开始

---

## 已完成（本次会话）

### 修复 pymodbus 3.13 API 兼容性
- mcp-servers/modbus-mcp/server.py — slave=1 改为 device_id=1，count 改为 keyword-only（6处）
- edge-gateway/src/app.py — 同样3处修复
- 环境/sim_plc.py — 重写为 SimDevice + SimData + DataType API

### 新建文件
- run_gateway.py — 边缘网关独立启动脚本
- .env — 含 DeepSeek API Key

### 运行中的服务
| 服务 | 端口 | 启动命令 |
|------|------|----------|
| Modbus 模拟器 | 502 | python 环境/sim_plc.py |
| InfluxDB 2.7 | 8086 | docker compose up -d influxdb |
| Grafana | 3000 | docker compose up -d grafana (admin/admin123) |

### 验证通过
- Modbus 模拟器读写(线圈/寄存器/离散输入)
- MCP Server 通过模拟器读写
- DeepSeek API 连通
- AI 闭环：采集->分析->决策->写入
- InfluxDB 数据写入

---

## 下一步：阶段 3 西门子工程态

### 已有条件
- TIA Portal V18: D:\TIA BEN TI\
- PLCSIM V18 + Advanced: D:\TIA FANG ZHEN\
- Openness API DLL: D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll

### 需要新建
- mcp-servers/tia-mcp/ — C# .NET TiaWorker + Python MCP Host
- plc-code-templates/siemens-scl/ — SCL代码生成Prompt模板

### 架构
Claude/Cursor -> TiaMcpHost(Python FastMCP) -> TiaWorker(C# .NET Framework 4.8) -> TIA Openness DLL

---

## 快速启动

cd "D:\claude code xiangmu\AI 接入PLC"
python 环境/sim_plc.py &          # 模拟器
docker compose up -d influxdb grafana  # 数据库+看板
python run_gateway.py              # 边缘网关
