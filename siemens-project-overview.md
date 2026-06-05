# 西门子 PLC 项目要点速查

## 关键路径（Windows）
| 项目 | 路径 |
|:----|:-----|
| TIA Portal V18 | `D:\TIA BEN TI\Portal V18\` |
| Openness API | `D:\TIA BEN TI\Portal V18\PublicAPI\V18\Siemens.Engineering.dll` |
| PLCSIM API | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\5.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll` |
| TIA 项目文件 | `D:\PLC cheng xu\TIA PLC CHENG XU\demo\demo.ap18` |
| CartGen | `mcp-servers/tia-mcp/CartGen/bin/Release/net8.0/CartGen.dll` |

## PLCSIM Advanced V5.0 铁律
- **任何 PowerOff 后实例无法再次启动**，必须重启电脑
- 保持 RUN 状态，勿关实例
- 更新程序时：TIA 切 STOP 下载，再切回 RUN
- 首次下载必须 TIA GUI 手动操作

## Factory IO
- 驱动：S7-PLCSIM → 实例名 `factoryio`，Softbus 连接
- GUI 必须保持运行，否则报 -4 DoesNotExist
- 控制台用 `\` 打开，实例名设单引号

## 安全红线
- 禁止 AI 操作急停回路
- 禁止修改 F-CPU 参数
- 所有控制指令必须影子仿真验证
- 连续 3 次异常值自动熔断
