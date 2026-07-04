# .ccb

本目录只承载 CCB + Codex + Claude Code 的协作层约束，不承载业务实现、PLC 逻辑或自动化执行入口。

## 第一阶段范围

- 只定义会话契约、变更边界、人工交接方式
- 不接入 hooks
- 不接入 orchestrator
- 不启用无人值守、自动轮询、自动锁

## 当前文件

- `session-contract.md`：会话内角色分工与交接约定
- `change-policy.md`：第一阶段允许与禁止的改动范围

## 暂不提供

- `ccb.config`
- 任何自动化 runner 配置
- 任何真实执行编排配置

真实 `ccb.config` 等文件格式在安装方式与配置规范确认后再补。
