# Current Chain Report - NL to PLCSIM 主链

> 更新时间：2026-07-04
> 目标链路：自然语言需求 → 生成 PLC 程序 → 导入 TIA → 编译 → 下载到 PLCSIM Advanced → snap7 读验证 → Factory I/O 可视化验证 → 前端一键触发

## 当前事实

- 第一阶段仿真目标：PLCSIM Advanced
- 固定实例名：`factoryio`
- 当前 PLC IP：`192.168.0.110`
- config.yaml 中 PLCSIM Advanced 默认 IP：`192.168.0.1`
- 当前 TIA 项目路径：`D:\PLC cheng xu\TIA PLC CHENG XU\demo_V21\demo_V21.ap21`
- 当前 TIA 安装目录：`D:\TIA BEN TI\Portal V21`
- 推断 TIA 版本：`V21`
- config.yaml 默认 TIA 版本：`V18`
- Factory I/O 可执行文件：`D:\Factory IO\Factory IO.exe`
- 端口 `8000-8005`：当前全部空闲

## 当前检查结果

- PASS：PLCSIM Advanced 安装目录存在
- PASS：DeepSeek API Key 可从项目 `.env` 被 `preflight.py` 读取
- PASS：Python 核心依赖可导入，包括 `python-snap7` 和 `pyyaml`
- PASS：Factory I/O 可执行文件存在
- PASS：端口 `8000-8005` 空闲
- FAIL：未检测到 TIA Portal 进程

## 当前为什么还不能跑完整真实链路

当前代码侧入口已经具备，但真实 TIA/PLCSIM 链路仍需要人工先打开 TIA Portal，并确认项目已加载。下一次真实验收前，先执行：

```powershell
D:/Python3/python.exe scripts/preflight.py --json
```

只有 TIA Portal 运行状态通过后，再进入 PLCSIM snap7 真实连接验证和完整 pipeline 冒烟。

## 已落地入口

- 后端 API：`POST /api/pipeline/nl-to-sim`
- orchestrator 工作流：`nl_to_plcsim_pipeline`
- 前端入口：`LadderGenerator` 中的 `生成并仿真`
- 事实报告脚本：`D:/Python3/python.exe scripts/current_chain_report.py --json`

## 下一步建议

1. 人工以管理员身份打开 TIA Portal，并加载当前 V21 项目。
2. 重新运行 `scripts/preflight.py --json`，确认只剩真实链路问题而不是环境问题。
3. 执行 PLCSIM snap7 只读验证，优先读 `M0.0`，第一轮不写入物理或真实设备。
4. 使用固定 prompt `三相异步电机正反转带急停和过载保护` 触发 `nl_to_plcsim_pipeline`。
5. snap7 通过后，再打开 Factory I/O 连接验证；动作级工艺验证放到下一轮。
