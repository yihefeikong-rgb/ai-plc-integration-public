# 西门子 SCL 代码模板库

AI 生成 PLC 代码时的 Prompt 模板，每个模板含完整 SCL 代码示例 + 命名规范 + 安全规则。

## 模板列表

| 文件 | 场景 | 复杂度 |
|:------|------|:------:|
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
| `冷冻站群控系统.md` | 冷冻站群控 + 冷机台数控制 + COP优化 | ⭐⭐⭐⭐ |
| `VAV变风量末端控制.md` | VAV变风量末端 + 房间温度PID + 风阀调节 | ⭐⭐⭐ |
| `恒压供水群控.md` | 恒压供水 + 多泵PID + 变频切换 + 休眠 | ⭐⭐⭐⭐ |
| `锅炉房热力站控制.md` | 锅炉热力站 + 供回水温度 + 气候补偿 | ⭐⭐⭐⭐ |
| `智能照明控制.md` | 智能照明 + 时间表 + 照度 + 人感联动 | ⭐⭐⭐ |
| `新风热回收控制.md` | 新风热回收 + 全热交换 + 旁通控制 | ⭐⭐⭐ |

## SCL 源文件

每个模板配套一个可直接编译的 `.scl` 源文件：

| 文件 | 功能块名称 | 说明 |
|------|-----------|------|
| `batch_counter.scl` | BatchCounter | 产品计数传感器上升沿计数 |
| `conveyor-with-timer.scl` | ConveyorWithTimer | 传送带多段延时控制 |
| `mixer.scl` | MixerControl | 搅拌罐状态机 |
| `tank_level.scl` | TankLevelControl | 液位控制 + 泵阀联动 |
| `traffic_light.scl` | TrafficLight | 交通灯状态机 + 四向黄闪 |
| `pid-control.scl` | PIDControl | PID 控制器 + 斜坡 + 抗饱和 + 无扰切换 |
| `pump-station.scl` | PumpStation | 多泵轮值 + 干转保护 |
| `packaging-machine.scl` | PackagingMachine | 包装机状态机 + 超时报警 |
| `sbr-process.scl` | SBRProcess | 污水 SBR 五阶段处理 |
| `cip-system.scl` | CIPSystem | CIP 自动清洗系统 |
| `cooling-tower.scl` | CoolingTower | 冷却塔多风机分级控制 |
| `电梯控制系统.scl` | ElevatorControl | 电梯集选控制 + 顺向截梯 |
| `停车场管理系统.scl` | ParkingManagement | 停车场出入口管理 |
| `楼宇自控HVAC系统.scl` | AHUControl | AHU新风机组 + PID + 防冻 |
| `冷冻站群控系统.scl` | ChillerPlant | 冷冻站群控 + COP优化 |
| `VAV变风量末端控制.scl` | VAVControl | VAV末端 + 房间温度PID |
| `恒压供水群控.scl` | WaterSupply | 恒压供水 + 多泵PID |
| `锅炉房热力站控制.scl` | BoilerStation | 锅炉热力站 + 气候补偿 |
| `智能照明控制.scl` | SmartLighting | 智能照明 + 时间表 + 人感 |
| `新风热回收控制.scl` | HeatRecovery | 新风热回收 + 旁通控制 |

## 引用的提示模板（在 server.py 的 _LAD_PROMPT_TEMPLATE 中）

用于 `generated_scl_code` 和 `generate_and_import` 工具的 template 参数：
- `motor` → motor-control.md
- `conveyor` → conveyor.md
- `pid` → pid-controller.md
- `cart` → material-cart.md（配套 `material_cart_plcopen.xml`）
- `general` → general.md（通用编程指南）

## 配套文件对照

| 模板 .md | 源文件 .scl | PLCopen XML |
|----------|-----------|-------------|
| motor-control.md | — | — |
| conveyor.md | conveyor-with-timer.scl | — |
| pid-controller.md | pid-control.scl | — |
| pump-station.md | pump-station.scl | — |
| packaging-machine.md | packaging-machine.scl | — |
| sbr-process.md | sbr-process.scl | — |
| cip-system.md | cip-system.scl | — |
| cooling-tower.md | cooling-tower.scl | — |
| material-cart.md | — | material_cart_plcopen.xml |

## 命名规范（所有模板通用）

- **数据类型前缀（匈牙利命名法）**:
  - `b` — Bool（如 `bEnable`, `bEmergencyStop`）
  - `w` — Word（如 `wCommand`）
  - `i` — Int（如 `iState`, `iFaultCode`）
  - `r` — Real（如 `rSpeed`, `rSetpoint`）
  - `t` — Time / Timer（如 `tDelay`）
  - `c_` — 状态常量（如 `c_STOP`, `c_RUN`）

- **输入输出命名**:
  - `i` / `I` 前缀 — 输入变量
  - `o` / `Q` 前缀 — 输出变量
  - `Fwd` / `Rev` — 正转/反转方向后缀

- **文件命名**:
  - 小写字母 + 连字符（如 `motor-control.md`）
  - 中文模板用中文文件名（如 `电梯控制系统.scl`）
  - 功能块名称用 PascalCase（如 `MotorControl`, `PIDControl`）

## LAD 模板（在 mcp-servers/tia-mcp/templates/ 中）

用于 `create_ladder_block` 工具的 21 个 LAD 模板：
见 `mcp-servers/tia-mcp/templates/` 目录

## 安全规则（所有模板通用）
1. 急停互锁（NOT bEmergencyStop → 安全降级：电机/阀门立即停止，交通灯四向黄闪）
2. 过载/过流保护
3. 正反转互锁
4. 输出限幅（模拟量）
5. 故障状态机（状态常量使用 c_XXX 命名，状态切换使用 CASE 语句）
6. 匈牙利命名法（bBool, rReal, iInt, tTime/tonTimer）
