# 阶段 1：运行态基础（Week 1-2）

> **目标**：让 AI 能够通过自然语言实时读取西门子 PLC、三菱 PLC 的数据。
> **前提**：你已有一台西门子 S7-1200/1500 或三菱 FX5U/Q 系列 PLC，且知道其 IP 地址。

---

## 今日快速验证（西门子 S7 + 笔记本电脑，2 小时跑通）

### Step 1：PLC 端配置（TIA Portal）

1. 打开 TIA Portal，进入项目
2. 设备组态 -> 双击 CPU -> 属性 -> **OPC UA** -> 勾选 **"激活 OPC UA 服务器"**
3. 设置服务器地址：默认 `opc.tcp://<PLC_IP>:4840`
4. 安全策略：先选 **"无"**（验证阶段，生产环境必须开加密）
5. 添加一个数据块 DB1，包含：
   ```
   DB1:
     Temperature : Real      // 温度
     Pressure    : Real      // 压力
     MotorSpeed  : Int       // 电机转速
     Running     : Bool      // 运行状态
   ```
6. **编译并下载到 PLC**

### Step 2：电脑端部署 MCP Server

```bash
# 1. 创建项目目录
mkdir -p ai-plc-integration/mcp-servers/opcua-mcp
cd ai-plc-integration/mcp-servers/opcua-mcp

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install fastmcp asyncua

# 4. 创建 server.py
cat > server.py << 'EOF'
from fastmcp import FastMCP
from asyncua import Client
import asyncio

mcp = FastMCP("siemens-opcua")

# 配置：修改为你的 PLC IP
PLC_URL = "opc.tcp://192.168.1.10:4840"
NAMESPACE = 3  # 西门子默认命名空间

@mcp.tool()
async def read_temperature() -> dict:
    """读取 PLC DB1 温度值（单位：摄氏度）"""
    try:
        async with Client(PLC_URL) as client:
            node = client.get_node(f"ns={NAMESPACE};s=DB1.Temperature")
            value = await node.read_value()
            return {"value": value, "unit": "°C", "status": "ok"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@mcp.tool()
async def read_pressure() -> dict:
    """读取 PLC DB1 压力值（单位：MPa）"""
    try:
        async with Client(PLC_URL) as client:
            node = client.get_node(f"ns={NAMESPACE};s=DB1.Pressure")
            value = await node.read_value()
            return {"value": value, "unit": "MPa", "status": "ok"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@mcp.tool()
async def read_motor_speed() -> dict:
    """读取 PLC 电机转速（单位：RPM）"""
    try:
        async with Client(PLC_URL) as client:
            node = client.get_node(f"ns={NAMESPACE};s=DB1.MotorSpeed")
            value = await node.read_value()
            return {"value": value, "unit": "RPM", "status": "ok"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@mcp.tool()
async def read_all() -> dict:
    """读取 PLC 所有关键数据"""
    try:
        async with Client(PLC_URL) as client:
            temp = await client.get_node(f"ns={NAMESPACE};s=DB1.Temperature").read_value()
            press = await client.get_node(f"ns={NAMESPACE};s=DB1.Pressure").read_value()
            speed = await client.get_node(f"ns={NAMESPACE};s=DB1.MotorSpeed").read_value()
            running = await client.get_node(f"ns={NAMESPACE};s=DB1.Running").read_value()
            return {
                "temperature": {"value": temp, "unit": "°C"},
                "pressure": {"value": press, "unit": "MPa"},
                "motor_speed": {"value": speed, "unit": "RPM"},
                "running": {"value": running, "unit": "bool"},
                "status": "ok"
            }
    except Exception as e:
        return {"error": str(e), "status": "failed"}

if __name__ == "__main__":
    mcp.run(transport='stdio')
EOF

# 5. 测试运行
python server.py
```

### Step 3：Claude Desktop 配置

编辑 `~/Library/Application Support/Claude/claude_desktop_config.json`（Mac）或 `%APPDATA%\Claude\claude_desktop_config.json`（Windows）：

```json
{
  "mcpServers": {
    "siemens-plc": {
      "command": "python",
      "args": ["/absolute/path/to/ai-plc-integration/mcp-servers/opcua-mcp/server.py"]
    }
  }
}
```

重启 Claude Desktop。

### Step 4：自然语言验证

在 Claude 中输入：
> "读取当前温度"
> "所有数据都读一遍"
> "电机转速多少"

你应该看到 AI 调用对应工具并返回实时数据。

---

## 三菱 MC 协议 MCP（无现成开源，必须自研）

### 三菱 PLC 端配置（GX Works3）

1. 打开 GX Works3，进入以太网端口设置
2. 设置 IP 地址（如 `192.168.1.20`）
3. 协议选择 **"MC 协议"**
4. 端口号：**5007**（默认）
5. 帧格式：**3E 帧**（ASCII 或 Binary，推荐 Binary）
6. 下载到 PLC

### 自研三菱 MCP Server

```bash
mkdir -p ai-plc-integration/mcp-servers/mitsubishi-mcp
cd ai-plc-integration/mcp-servers/mitsubishi-mcp
python -m venv venv
source venv/bin/activate
pip install fastmcp
```

```python
# server.py
from fastmcp import FastMCP
import socket
import struct

mcp = FastMCP("mitsubishi-mc")

PLC_IP = "192.168.1.20"
PLC_PORT = 5007

class McProtocol:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def _build_read_cmd(self, device, device_no, count, is_word=True):
        """构建 MC 协议 3E 帧读取命令（Binary）"""
        header = bytes([0x50, 0x00])
        network = bytes([0x00])
        pc = bytes([0xFF])
        io = bytes([0xFF, 0x03])
        data_len = 12 + count * 2
        timer = bytes([0x10, 0x00])
        cmd = bytes([0x01, 0x04])
        subcmd = bytes([0x00, 0x00]) if is_word else bytes([0x01, 0x00])
        dev_code = device.encode()
        addr_bytes = struct.pack('<I', device_no)[:3]
        count_bytes = struct.pack('<H', count)
        frame = (header + network + pc + io + 
                 struct.pack('<H', data_len) + timer + cmd + subcmd +
                 addr_bytes + dev_code + count_bytes)
        return frame

    def read(self, device, count=1):
        """读取寄存器，如 read('D100', 1) 读取 D100"""
        dev_type = ''.join([c for c in device if c.isalpha()])
        dev_no = int(''.join([c for c in device if c.isdigit()]))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5)
            s.connect((self.host, self.port))
            s.send(self._build_read_cmd(dev_type, dev_no, count))
            response = s.recv(1024)
            if len(response) < 11:
                return {"error": "响应太短", "raw": response.hex()}
            end_code = struct.unpack('<H', response[9:11])[0]
            if end_code != 0:
                return {"error": f"错误码: {end_code:04X}"}
            data = response[11:]
            values = [struct.unpack('<h', data[i:i+2])[0] for i in range(0, len(data), 2)]
            return {"values": values, "status": "ok"}

plc = McProtocol(PLC_IP, PLC_PORT)

@mcp.tool()
def read_register(device: str, count: int = 1) -> dict:
    """读取三菱 PLC 寄存器，如 'D100'、'M0'、'X0'、'Y0'"""
    return plc.read(device, count)

@mcp.tool()
def read_temperature() -> dict:
    """读取温度值（假设在 D100）"""
    result = plc.read("D100", 1)
    if result.get("status") == "ok":
        return {"value": result["values"][0], "unit": "°C", "status": "ok"}
    return result

if __name__ == "__main__":
    mcp.run(transport='stdio')
```

---

## 无硬件验证方案（OpenPLC 仿真）

如果你没有实体 PLC，用 OpenPLC Docker 验证：

```bash
# 1. 启动 OpenPLC
docker run -d -p 8080:8080 -p 502:502 --name openplc thiagoralves/openplc:v3

# 2. 访问 http://localhost:8080，默认账号 openplc / openplc
# 3. 上传一个简单程序（如 blink.st），编译并启动
# 4. 用 Modbus TCP 连接 localhost:502 测试

# 5. 部署 Modbus MCP
pip install pymodbus fastmcp
```

```python
# modbus_mcp_server.py
from fastmcp import FastMCP
from pymodbus.client import ModbusTcpClient

mcp = FastMCP("modbus-plc")
client = ModbusTcpClient("localhost", port=502)

@mcp.tool()
def read_holding_register(address: int, count: int = 1) -> dict:
    """读取保持寄存器（4x），地址从 0 开始"""
    result = client.read_holding_registers(address, count)
    if result.isError():
        return {"error": str(result)}
    return {"values": result.registers, "status": "ok"}

@mcp.tool()
def write_holding_register(address: int, value: int) -> dict:
    """写入保持寄存器"""
    result = client.write_register(address, value)
    if result.isError():
        return {"error": str(result)}
    return {"status": "ok", "written": value}

if __name__ == "__main__":
    client.connect()
    mcp.run(transport='stdio')
```

---

## 本周检查清单

- [ ] OPC UA MCP 能读取西门子 PLC 实时数据
- [ ] 三菱 MC 协议 MCP 能读取寄存器（如有三菱 PLC）
- [ ] Claude/Cursor 中自然语言指令能触发工具调用
- [ ] 所有工具返回 JSON 结构化数据
- [ ] 错误处理完善（超时、断线、权限）
- [ ] 代码已提交 Git，README 完整
