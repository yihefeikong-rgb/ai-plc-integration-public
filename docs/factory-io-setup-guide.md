# Factory I/O ↔ PLCSIM Advanced 接入指南

> 让 AI 生成的控制逻辑在 3D 虚拟工厂里跑起来。

---

## 架构

```
┌──────────────┐     Softbus/TCPIP     ┌──────────────────┐
│  Factory I/O  │ ←──────────────────→ │  PLCSIM Advanced  │
│  3D 虚拟工厂   │   传感器/执行器数据     │  虚拟 S7-1500     │
└──────────────┘                       └────────┬─────────┘
                                                 │
                                        TIA Portal 下载
                                                 │
                                        ┌────────▼─────────┐
                                        │   TIA Portal V18  │
                                        │   OB1 + FB 逻辑   │
                                        └──────────────────┘
```

## 两种连接方式

| | 方式 A: S7-PLCSIM (Softbus) | 方式 B: S7-1200/1500 (TCP/IP) |
|---|---|---|
| Factory I/O 驱动 | `Siemens S7-PLCSIM` | `Siemens S7-1200/1500` |
| Model 选择 | `S7-1500 (S7-PLCSIM Advanced)` | `S7-1500` |
| 通信 | 本机 API 直连（Softbus） | S7 协议 TCP/IP:102 |
| 实例名要求 | **必须叫 `factoryio`** | 任意 |
| 网络配置 | 无 | IP + 虚拟网卡 |
| 推荐场景 | 快速验证 | 接近真实环境 |

**推荐方式 A（Softbus）先跑通，没网络坑。**

---

## 步骤 1：PLCSIM Advanced 配置

### 方式 A (Softbus) — 推荐

1. 打开 PLCSIM Advanced 控制面板
2. **实例名改为 `factoryio`**（Factory I/O 硬编码要求）
3. 点击 Start
4. 状态灯变绿 → OK

```
实例设置:
  Name:      factoryio
  IP:        不需要（Softbus 模式）
  Subnet:    不需要
  PLC Type:  S7-1500 (自动)
```

### 方式 B (TCP/IP) — 沿用现有配置

确保虚拟网卡已配置：
```powershell
# 确认 IP（如失效重新设置）
netsh interface ip show addresses "以太网 2"
# 如需要:
netsh interface ip set address "以太网 2" static 10.0.0.200 255.255.255.0
```

PLCSIM Advanced 实例：
```
Name:      任意（如 s7-1500）
Mode:      TCP/IP <Local>
IP:        192.168.0.1
Subnet:    255.255.255.0
```

验证：
```powershell
ping 192.168.0.1          # 应 <1ms
Test-NetConnection 192.168.0.1 -Port 102  # 应 True
```

---

## 步骤 2：TIA Portal 准备

### 2.1 下载 PLC 程序到 PLCSIM Advanced

1. 打开 TIA Portal 项目
2. 右键 CPU → Download to device → Hardware and software
3. PG/PC interface 选择：
   - 方式 A: `PC Internal (Softbus)`
   - 方式 B: `Siemens PLCSIM Virtual Ethernet Adapter`
4. Load → Start module

### 2.2 启用仿真编译

1. 右键项目名 → Properties → Protection
2. ✅ 勾选 `Support simulation during block compilation`

### 2.3 生成 IO 标签（用 fio_mapper.py）

```bash
cd mcp-servers/tia-mcp
python fio_mapper.py --offset 10
```

按提示输入 Factory I/O 驱动窗口显示的传感器/执行器名称（按顺序！）。

这会生成：
- `D:\TIA FANG ZHEN\fio_tags.xml` — TIA Portal 可导入的标签表
- `D:\TIA FANG ZHEN\fio_tags.csv` — CSV 备选
- `D:\TIA FANG ZHEN\fio_ob1_skeleton.scl` — OB1 控制逻辑骨架

### 2.4 导入标签到 TIA Portal

1. TIA Portal → PLC Tags → 右键 → Import
2. 选择 `fio_tags.xml`
3. 标签表名设为 `Factory IO Tags`

### 2.5 编写 OB1 控制逻辑

打开 `fio_ob1_skeleton.scl`，在标记处编写控制逻辑。

**简单示例（Sorting by Height）：**
```pascal
// 入口传送带：有盒子且出口传送带没满时启动
IF "FIO_I_At_Entry" AND NOT "FIO_Q_Conveyor_Exit" THEN
    "FIO_Q_Conveyor_Entry" := TRUE;
ELSE
    "FIO_Q_Conveyor_Entry" := FALSE;
END_IF;

// 高度分拣：盒子到达分拣位
IF "FIO_I_At_Height" THEN
    "FIO_Q_Conveyor_Entry" := FALSE;  // 停入口传送带

    IF "FIO_I_BoxL" THEN
        "FIO_Q_Pusher_Left" := TRUE;  // 大盒推左
    ELSIF "FIO_I_BoxM" THEN
        "FIO_Q_Pusher_Mid" := TRUE;   // 中盒推中
    ELSIF "FIO_I_BoxS" THEN
        "FIO_Q_Conveyor_Exit" := TRUE; // 小盒直走
    END_IF;
END_IF;
```

---

## 步骤 3：Factory I/O 连接

### 3.1 打开场景

Factory I/O → Scenes → `Sorting by Height (Basic)`

### 3.2 配置驱动

按 F4 打开驱动窗口。

#### 方式 A: S7-PLCSIM (Softbus)

| 设置 | 值 |
|------|-----|
| Driver | `Siemens S7-PLCSIM` |
| Model | `S7-1500 (S7-PLCSIM Advanced)` |
| Auto connect | ✅ |

> 如果实例名不是 factoryio，用控制台改：
> 按 ` 打开控制台，输入 `drivers.siemens_s7plcsim.instance_name = '你的实例名'`

#### 方式 B: S7-1200/1500 (TCP/IP)

| 设置 | 值 |
|------|-----|
| Driver | `Siemens S7-1200/1500` |
| Model | `S7-1500` |
| Host | `192.168.0.1` |
| Bool Inputs offset | `10` |
| Bool Inputs count | 根据传感器数 |
| Bool Outputs offset | `10` |
| Bool Outputs count | 根据执行器数 |

### 3.3 连接

点击 CONNECT → 绿色图标 = 成功 ✅

---

## 步骤 4：运行验证

1. Factory I/O → 按 F5 运行（或工具栏 ▶ 按钮）
2. PLC 应该在 RUN 模式（PLCSIM Advanced 面板确认）
3. 观察 3D 场景中的传感器和执行器是否正常工作

### 故障排查

| 症状 | 可能原因 | 检查 |
|------|---------|------|
| Factory I/O 连不上 | 实例名不对 | PLCSIM Advanced 实例名必须是 `factoryio`（方式A） |
| | IP 不通 / 端口不对 | `ping 192.168.0.1` + `Test-NetConnection 192.168.0.1 -Port 102`（方式B）|
| | TIA Portal 没下载 | 确认已下载到 PLCSIM Advanced |
| 连上了但 IO 不动 | 偏移量不匹配 | Factory I/O 驱动 offset 和 OB1 中的 %I/%Q 地址要一致 |
| | 标签没导入 | TIA Portal 确认标签表中存在对应标签 |
| | PLC 不在 RUN | PLCSIM Advanced 面板切换到 RUN |
| 传感器读不到 | PUT/GET 未启用 | 方式B: CPU 属性 → Protection → ✅ Permit PUT/GET |

---

## IO 映射原理

Factory I/O 的传感器/执行器列表顺序决定地址映射：

```
Factory I/O 传感器（按驱动窗口顺序）:
  [0] At Entry        → %I10.0     (offset=10, 第0个)
  [1] At Exit         → %I10.1
  [2] BoxS (Height)   → %I10.2
  [3] BoxM (Height)   → %I10.3
  [4] BoxL (Height)   → %I10.4
  [5] At Left         → %I10.5
  [6] At Right        → %I10.6
  [7] Start Button    → %I10.7
  [8] Stop Button     → %I11.0     (跨字节)

Factory I/O 执行器（按驱动窗口顺序）:
  [0] Conveyor Entry  → %Q10.0
  [1] Conveyor Left   → %Q10.1
  [2] Conveyor Right  → %Q10.2
  [3] Start Light     → %Q10.3
  [4] Stop Light      → %Q10.4
```

**关键规则：**
- 顺序 = Factory I/O 驱动窗口中的顺序（一般是场景中从左到右、从上到下）
- 地址 = `%I/{I_offset + index/8}.{index%8}`
- 偏移量 10 是为了避开物理输入模块使用的低地址

---

## 下一步：AI 生成控制逻辑

打通连接后，就可以让 AI 根据场景自动生成 OB1 控制逻辑：

```
你说: "Sorting by Height 场景，入口传感器触发传送带，
       高度传感器区分大中小，分别推到左中右通道"

     ↓ full_pipeline() 扩展
     
AI 生成 OB1 SCL → TIA Portal 编译 → 下载 → Factory I/O 验证
```

这条链路就是阶段 3 的最终目标。
