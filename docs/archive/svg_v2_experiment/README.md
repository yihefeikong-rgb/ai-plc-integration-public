# SVG V2 实验代码归档

归档时间: 2026-06-18

## 来源

这些文件来自 Reasonix 在 mcp-servers/tia-mcp/ 下的 SVG 梯形图渲染实验。

## 核心文件

| 文件 | 说明 |
|------|------|
| svg_renderer_v2.py | SVG 渲染器（从 RenderTree 生成 SVG） |
| demo_svg_v2.py | 演示脚本（生成 4 个示例 SVG） |
| ast_svg_generator.py | 后端 SVG 生成器 |
| LadderSvgRenderer.jsx | 前端 SVG 渲染组件 |

## 示例 SVG

| 文件 | 场景 |
|------|------|
| ConveyorControl.svg | 传送带控制 |
| MotorControl.svg | 电机控制 |
| SimpleSeries.svg | 简单串联 |
| TimerCounterDemo.svg | 定时器计数器 |

## 调试/辅助

diagnose_renderer.py, fix_commas.py, fix_diag.py, run_acceptance.py,
acceptance_output/, *.txt 调试输出

## 何时重启

当 ASCII-LAD-V2 规范成熟、用户量增长需要图片导出时：

```
ASCII-LAD-V2 → ascii_parser.py → LadderModel → SVG Renderer
```

保留在 mcp-servers/tia-mcp/ 中的 TIA 管线文件（lad_ast.py, layout_engine.py, render_tree.py）
可作为 SVG 渲染的基础复用。
