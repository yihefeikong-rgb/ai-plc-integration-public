# 发布门槛检查清单

> 日期：2026-07-22
> 状态：追踪中

## 单元测试

- [x] 工具注册表测试（B1.5）
- [x] 参数校验测试（B1.5）
- [x] 路径限制测试（B1.1, B1.5）
- [x] 风险等级测试（B3.0）
- [x] Preview Token 测试（B4.2）
- [x] 统一返回格式测试（B1.3, B1.5）
- [x] 工作流引擎测试（B5.1）

## 集成测试

- [ ] 连接 TIA Portal（需 TIA 环境）
- [ ] 列出设备
- [ ] 列出块
- [ ] 导出块
- [ ] 解析 Network
- [ ] 导入新块
- [ ] 编译项目
- [ ] 恢复原项目

## 安全审查

- [x] 默认离线测试通过（B1.5）
- [x] Gateway 工具注册无冲突（B3.0）
- [x] 写操作有 Preview/Apply（B4.2）
- [x] 修改前有备份机制（B4.2）
- [ ] 编译失败有回滚（B4.1 骨架）

## 文档

- [x] 架构决策：ADR-001（单 Gateway）
- [x] 架构决策：ADR-002（TiaCommander 采用）
- [x] 能力矩阵：`mcp-capability-matrix.md`
- [x] 工具归属：`mcp-tool-ownership.md`
- [x] 迁移映射：`mcp-migration-map.md`
- [x] Provider 能力矩阵：`mcp-provider-capability-matrix.md`
- [x] TiaCommander 评估：`integrations/tiacommander-local-assessment.md`

## 待办事项

- [ ] 将 TiaCommander 二进制从仓库目录移除
- [ ] 向作者确认集成条款
- [ ] 完成 TiaCommander V21 兼容性测试
- [ ] 实现 Provider Router 的 TiaCommander 适配器
- [ ] 实现网络级 Patch 的实际执行（TiaCommander 或 TiaWorker 扩展）
- [ ] 添加 E2E 测试（需 TIA 环境）
- [ ] 更新 README 中的动态验收状态