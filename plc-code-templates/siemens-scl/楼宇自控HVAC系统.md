# 楼宇自控HVAC — AHU新风机组控制 (AHUControl)

## 功能概述

中央空调新风机组（AHU）全功能控制，含制冷/制热/通风/防冻四模式自动切换、PID温度调节、CO2新风控制、过滤器监控。

## 适用场景

- 商业楼宇、办公楼、酒店、医院的新风机组控制
- 定风量（CAV）或变风量（VAV）空调系统
- 四管制或两管制水系统

## 接口定义

### 输入
| 信号 | 类型 | 说明 |
|------|------|------|
| bEnable | Bool | 系统使能 |
| bReset | Bool | 故障复位 |
| bEmergencyStop | Bool | 急停（常闭） |
| bManualMode | Bool | 手动模式 |
| bSupplyFanRun / bReturnFanRun | Bool | 送/回风机运行反馈 |
| bFanOverload | Bool | 风机过载 |
| rReturnAirTemp | Real | 回风温度 (°C) |
| rSupplyAirTemp | Real | 送风温度 (°C) |
| rOutdoorAirTemp | Real | 室外温度 (°C) |
| rCO2Level | Real | CO2浓度 (ppm) |
| rFilterPressure | Real | 过滤器压差 (Pa) |
| rFreezeProtectTemp | Real | 防冻传感器温度 |
| bFreezeStat | Bool | 防冻开关 |
| bOccupied / bHoliday | Bool | 占用模式/节假日 |
| rCoolSetpoint / rHeatSetpoint | Real | 制冷/制热设定温度 |
| rCO2Setpoint | Real | CO2设定值 |

### 输出
| 信号 | 类型 | 说明 |
|------|------|------|
| bSupplyFanCmd / bReturnFanCmd | Bool | 送/回风机启停 |
| bChilledWaterValve / bHotWaterValve | Real | 冷水阀/热水阀开度 |
| rFreshAirDamper / rReturnAirDamper | Real | 新风阀/回风阀开度 |
| bFilterAlarm / bFreezeAlarm / bFanAlarm | Bool | 故障报警 |
| bCoolMode / bHeatMode | Bool | 制冷/制热模式 |
| sMode | String | 当前模式 |

## 模式切换

| 模式 | 条件 | 说明 |
|:----:|------|------|
| OFF | !bOccupied 或 bHoliday | 停机，60s延时切换 |
| COOL | 回温 > 设定+1°C | PID调节冷水阀，CO2控新风 |
| HEAT | 回温 < 设定-1°C | PID调节热水阀，新风最小化 |
| VENT | 温度在滞回区 | 仅通风，水阀关闭 |
| FREEZE | 温度<5°C或防冻开关 | 全开热水阀，停风机，关新风 |

## 控制策略

1. **模式滞回**：温度在±1°C滞回区内维持当前模式，防止频繁切换
2. **PID调节**：回风温度→供水阀开度，积分分离+抗饱和
3. **CO2新风控制**：CO2超标时新风阀从30%开至100%
4. **风机联锁**：送风机启动5s后启动回风机，风机未运行不开水阀
5. **时间表**：非占用模式/节假日→停机
6. **防冻优先**：防冻条件触发→全开热水阀，停风机，关新风

## 安全规则

1. 急停无条件中断所有输出
2. 防冻逻辑优先级最高（水温<5°C强制保护）
3. 风机过载自动停机，需手动复位
4. 过滤器压差>250Pa延时60s报警
5. 模式切换带30-60s延时防抖
