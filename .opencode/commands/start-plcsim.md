# project:start-plcsim — 启动 PLCSIM + Factory IO

启动 PLCSIM Advanced V5.0 实例和 Factory IO 连接。

## 步骤

### 1. 检查 PLCSIM 状态
- RUN python mcp-servers/tia-mcp/plcsim_api.py list

### 2. 如实例不存在，创建并启动
- RUN python mcp-servers/tia-mcp/plcsim_api.py create factoryio 10.0.0.1 1516

### 3. 检查 Factory IO auto.cfg
- READ C:\ProgramData\Real Games\Factory IO\auto.cfg

### 4. 启动 Factory IO（如已安装）
- RUN start "" "C:\Program Files (x86)\Real Games\Factory I-O\Factory I-O.exe"

## 注意事项
- ⚠️ **PLCSIM Advanced GUI 必须保持打开**，否则 Factory IO 报 -4
- ⚠️ **不要 PowerOff 实例**，保持 RUN 状态
- ⚠️ 实例名必须匹配：`factoryio`（Factory IO 控制台需同步设置）
- 如需重启实例，使用黄金备份恢复，不是 PowerOff
