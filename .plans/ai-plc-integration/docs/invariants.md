# 不可破坏约束 — AI 接入 PLC

> 这些是系统的硬边界。任何 agent 在实现前必须读取并遵守。违反任一条 = BLOCK。

---

## 运行安全（不可破坏）

### INV-1：禁止 AI 操作急停回路
- 急停回路地址段：安全 PLC（F-CPU）所有 IO
- 任何 AI 写入请求不得涉及急停相关地址
- 违反后果：BLOCK，不允许合并

### INV-2：禁止 AI 修改安全 PLC 参数
- F-CPU 的所有配置参数（硬件配置、安全程序）禁止 AI 写入
- 违反后果：BLOCK

### INV-3：所有控制指令必须经过影子仿真
- 写入操作前，先在 shadow_simulator 中验证结果
- 仿真结果与预期不符 → 拦截写入
- 违反后果：BLOCK

### INV-4：生产环境写入需双人确认
- 操作人和确认人不能是同一人
- 涉及安全写入（互锁/急停除外）需要二次确认
- 违反后果：BLOCK

### INV-5：审计日志不可篡改
- 所有写入操作记录到审计日志
- 使用 HMAC 链式哈希保证完整性
- 任何修改审计日志的行为 = 安全事件
- 违反后果：BLOCK

## 配置安全

### INV-6：修改全局配置前必须备份
- 修改 `~/.claude/settings.json` 前备份到 `~/.claude/settings.json.bak`
- 显示 diff 预览，获得用户确认
- 违反后果：WARN，需回滚

### INV-7：安装 git hooks 前必须预览
- 列出要安装的 hook 内容
- 获得用户明确同意
- 违反后果：WARN

## 开发环境

### INV-8：Python 解释器固定
- 必须使用 `D:\Python3\python.exe` (3.13.2)
- 不允许使用其他 Python 版本或虚拟环境路径
- 违反后果：WARN（可能导致依赖不兼容）

### INV-9：TIA Portal 版本固定
- 主版本：V21
- 不允许降级到 V18 或更低版本操作
- 违反后果：BLOCK（可能导致项目文件损坏）

## 数据完整性

### INV-10：ChromaDB 路径固定
- 正确路径：`ai-plc-assistant/backend/data/vector_db`
- 常见错误：以为是 `data/chroma_db`
- 违反后果：WARN（知识库不可用）

### INV-11：PLCSIM 实例名不超过 8 字符
- PLCSIM Advanced 限制
- 违反后果：WARN（PLCSIM 启动失败）

## 代码质量

### INV-12：安全相关代码必须经过 reviewer 独立审查
- developer 和 reviewer 不能是同一 agent
- 涉及 safety/ 目录、写入操作、互锁规则的变更
- 违反后果：BLOCK