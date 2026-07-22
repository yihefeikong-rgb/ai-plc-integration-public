# TiaCommander vs TiaWorker 能力对照矩阵

> 日期：2026-07-22
> 状态：基于文档分析，未授权下未经验证

## 对照总览

| 维度 | TiaCommander | TiaWorker | 说明 |
|------|-------------|-----------|------|
| 许可证 | 专有软件（免费 Beta） | 开源（项目自有） | TiaWorker 无许可证风险 |
| 版本 | 2.29.0 | 项目内建 | TiaWorker 版本可控 |
| TIA 支持 | V15.1–V21（仅 V19 测试） | V21 验证 | TiaWorker 更匹配项目目标 |
| 工具数 | 16 工具 / 166 动作 | 50+ 命令 | TiaWorker 底层命令更丰富 |
| 当前状态 | 未授权（仅 2 工具可用） | 可用 | TiaWorker 可立即使用 |
| 运行方式 | 外部 .exe 二进制 | C# 项目编译 | TiaWorker 可审计可修改 |
| 协议支持 | MCP stdio | MCP stdio | 两者一致 |

## 能力逐项对比

### 项目管理

| 能力 | TiaCommander | TiaWorker | 建议 Provider |
|------|-------------|-----------|--------------|
| 列出项目 | ✅ | ✅ | 两者均可 |
| 打开项目 | ✅ | ✅ | 两者均可 |
| 保存项目 | ✅ | ✅ | TiaWorker |
| 归档项目 | ✅ | ✅ | TiaWorker |
| 关闭项目 | ✅ | ✅ | TiaWorker |

### 块操作

| 能力 | TiaCommander | TiaWorker | 建议 Provider |
|------|-------------|-----------|--------------|
| 列块 | ✅ | ✅ | 两者均可 |
| 块详情 | ✅ | ✅ | 两者均可 |
| 块接口 | ✅ | ✅ | 两者均可 |
| 读取 XML | ✅ raw + parsed | ✅ | 两者均可 |
| 导出 XML | ✅ inline | ✅ file | 两者均可 |
| 导出源代码 | ✅ | ❌ | TiaCommander |
| 一致性检查 | ✅ | ✅ | 两者均可 |
| 编译器错误 | ✅ | ✅ | 两者均可 |
| 创建空块 | ✅ | ✅ | TiaWorker |
| 创建带接口块 | ✅ LAD/SCL/FBD/STL | ✅ LAD/SCL | 两者均可 |
| 导入 XML | ✅ | ✅ | TiaWorker |
| 删除块 | ✅ | ✅ | TiaWorker |
| 网络级操作 | ✅ add/update/replace/delete | ❌ | TiaCommander* |
| 修改调用目标 | ✅ | ❌ | TiaCommander* |
| 修改实例 DB | ✅ | ❌ | TiaCommander* |

\* 网络级操作：TiaCommander 已实现，TiaWorker 尚未。若 TiaCommander 授权不可用，需在 TiaWorker 中实现。

### 标签和数据类型

| 能力 | TiaCommander | TiaWorker | 建议 Provider |
|------|-------------|-----------|--------------|
| 标签表操作 | ✅ | ✅ | 两者均可 |
| UDT 操作 | ✅ | ✅ | 两者均可 |
| Watch 表 | ✅ | ✅ | 两者均可 |

### 硬件和诊断

| 能力 | TiaCommander | TiaWorker | 建议 Provider |
|------|-------------|-----------|--------------|
| 硬件配置读取 | ✅ | ✅ | 两者均可 |
| 交叉引用 | ✅ | ✅ | 两者均可 |
| 调用关系 | ✅ | ✅ | 两者均可 |
| 在线诊断 | ✅ | ✅ 部分 | TiaCommander |
| 连接配置 | ✅ | ❌ | TiaCommander |
| 在线状态 | ✅ | ❌ | TiaCommander |

### 下载和部署

| 能力 | TiaCommander | TiaWorker | 建议 Provider |
|------|-------------|-----------|--------------|
| 下载到设备 | ✅ | ✅ | TiaWorker |
| 上传站点 | ✅ | ❌ | TiaCommander |
| 设备扫描 | ✅ | ❌ | TiaCommander |

### AI 工程能力

| 能力 | TiaCommander | TiaWorker 生态 | 建议 Provider |
|------|-------------|---------------|--------------|
| LadderSpec 生成 | ❌ | ✅ LadderSpec | TiaWorker |
| LAD AST | ❌ | ✅ lad_ast.py | TiaWorker |
| ASCII-LAD | ❌ | ✅ ladder_renderer.py | TiaWorker |
| CartGen LAD 生成 | ❌ | ✅ CartGen.dll | TiaWorker |
| SCL Lint | ❌ | ✅ scl_lint.py | TiaWorker |
| SimaticML 生成 | ❌ | ✅ CartGen | TiaWorker |
| 语义安全检查 | ❌ | ✅ safety/ | TiaWorker |
| PLCSIM 管理 | ❌ | ✅ plcsim_*.py | TiaWorker |
| Golden Backup | ❌ | ✅ plcsim_backup.py | TiaWorker |
| Factory I/O | ❌ | ✅ tools_pipeline.py | TiaWorker |

### 安全和审计

| 能力 | TiaCommander | TiaWorker 生态 | 建议 Provider |
|------|-------------|---------------|--------------|
| 目标校验 | 基础 | ✅ validate_control_target | TiaWorker |
| 操作审计 | ❌ | ✅ audit_log | TiaWorker |
| Preview/Apply | 基础 | ✅ _PreviewStore | TiaWorker |
| 人工确认 | 仅下载/上传 | ✅ 完整链 | TiaWorker |
| 风险等级 | ❌ | ✅ L0-L4 | TiaWorker |
| 回滚 | ❌ | ✅ Golden Backup | TiaWorker |

## 不适合 TiaCommander 的能力

以下能力是 TiaWorker 生态独有的，TiaCommander 无法替代：

1. **LadderSpec 流程** — 自然语言 → LAD 的完整 AI 生成管线
2. **LAD AST / ASCII-LAD** — 梯形图解析和可视化
3. **CartGen** — LAD XML 生成器
4. **SCL Lint** — SCL 代码静态分析
5. **语义安全链** — `safety/validator` + `test_ladder_semantic_safety.py`
6. **PLCSIM Advanced 管理** — 实例创建/恢复/黄金备份
7. **Factory I/O 集成** — 3D 仿真场景联动
8. **snap7 只读核验** — 下载后验证

## 结论

### 适合 TiaCommander 的候选（获得授权后）
- 块 XML 读取（`get_xml_raw` 比 TiaWorker 更直接）
- 网络级修改（`add_network`、`replace_network` 等）
- 在线诊断和连接配置
- 设备扫描和上传
- 调用关系分析

### 必须由 TiaWorker 承担
- 所有 AI 工程能力（LadderSpec、CartGen、SCL Lint）
- 所有安全链（目标校验、审计、Preview/Apply、风险等级）
- PLCSIM 和 Factory I/O 集成
- 所有写操作的最终执行

### 当前建议
由于 TiaCommander 未授权且使用 V18 API（项目目标 V21），**所有能力当前只能由 TiaWorker 承担**。TiaCommander 的验证推迟到获得授权和 V21 测试环境准备就绪后。