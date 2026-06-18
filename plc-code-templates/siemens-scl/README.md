# 西门子 SCL 代码模板库

AI 生成 PLC 代码时的 Prompt 模板，每个模板含完整 SCL 代码示例 + 命名规范 + 安全规则。

## 模板列表

| 文件 | 场景 | 复杂度 |
|:------|------|:------:|
|------|------|:------:|
| `motor-control.md` | 电机正反转 + 急停 + 过载 + 限位 | ⭐⭐ |
| `conveyor.md` | 多段传送带 + 堵料检测 + 满料停止 | ⭐⭐ |
| `pid-controller.md` | PID 控制器 + 积分分离 + 抗饱和 + 斜坡 + PID_Compact 封装 | ⭐⭐⭐ |
| `pump-station.md` | 多泵轮值 + 液位分档 + 干转保护 + Duty 轮换 | ⭐⭐⭐ |
| `packaging-machine.md` | 包装机状态机 + 批次计数 + 超时报警 + 故障码 | ⭐⭐⭐ |
| `sbr-process.md` | SBR 污水处理 + 五阶段时序 + DO 分档曝气 + 参数可配 | ⭐⭐⭐ |
| `cip-system.md` | CIP 清洗系统 + 五阶段清洗 + 温度控制 + 电导率监控 | ⭐⭐⭐⭐ |
| `cooling-tower.md` | 冷却塔 + 多风机分级 + VFD + 冷机联锁 + 防冻 | ⭐⭐⭐⭐ |
| `电梯控制系统.md` | 电梯集选控制 + 顺向截梯 + 门控时序 + 消防归底 | ⭐⭐⭐⭐ |
| `停车场管理系统.md` | 停车场出入口 + 车位计数 + 防砸 + 满位控制 | ⭐⭐⭐ |
| `楼宇自控HVAC系统.md` | AHU新风机组 + 制冷/制热/防冻 + PID + CO2新风 | ⭐⭐⭐⭐ |

## SCL 源文件

每个模板配套一个可直接编译的 `.scl` 源文件：

| 文件 | 功能块名称 | 说明 |
|------|-----------|------|
| `batch_counter.scl` | BatchCounter | 产品计数传感器上升沿计数（已有） |
| `conveyor-with-timer.scl` | ConveyorWithTimer | 传送带多段延时控制（已有） |
| `mixer.scl` | MixerControl | 搅拌罐状态机（已有） |
| `tank_level.scl` | TankLevelControl | 液位控制 + 泵阀联动（已有） |
| `traffic_light.scl` | TrafficLight | 交通灯状态机循环（已有） |
| `pid-control.scl` | PIDControl | PID 控制器 + 斜坡 + 抗饱和 |
| `pump-station.scl` | PumpStation | 多泵轮值 + 干转保护 |
| `packaging-machine.scl` | PackagingMachine | 包装机状态机 + 超时报警 |
| `sbr-process.scl` | SBRProcess | 污水 SBR 五阶段处理 |
| `cip-system.scl` | CIPSystem | CIP 自动清洗系统 |
| `cooling-tower.scl` | CoolingTower | 冷却塔多风机分级控制 |
| `电梯控制系统.scl` | ElevatorControl | 电梯集选控制 + 顺向截梯 |
| `停车场管理系统.scl` | ParkingManagement | 停车场出入口管理 |
| `楼宇自控HVAC系统.scl` | AHUControl | AHU新风机组 + PID + 防冻 |

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
1. 急停互锁（NOT bEmergencyStop → 无条件停止）
2. 过载/过流保护
3. 正反转互锁
4. 输出限幅（模拟量）
5. 故障状态机（状态常量使用 c_XXX 命名，状态切换使用 CASE 语句）
6. 匈牙利命名法（bBool, rReal, iInt, tTime/tonTimer）
