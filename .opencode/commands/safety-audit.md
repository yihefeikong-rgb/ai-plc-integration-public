# project:safety-audit — 生成安全审核报告

分析审计日志、检查安全互锁规则、生成安全报告（只读）。

## 步骤

### 1. 读取审计日志
- READ logs/audit.log（最新 50 条）

### 2. 检查安全配置
- READ safety/validator.py（验证 FORBIDDEN_PATTERNS、CONFIRM_PATTERNS、safety_max_errors）
- READ safety/audit.py（确认审计机制）
- READ safety/interlock-rules.yml（如果存在）

### 3. 检查环境配置
- READ .env（安全相关配置，不输出敏感值）

### 4. 输出报告

```markdown
## 🔒 安全审计报告

### 审计日志完整性
- ✅ 日志链验证：[通过/失败]
- 总记录数：N 条
- 最新记录：[timestamp] — [action] — [target]

### 互锁规则配置
- 禁止写入模式：N 条
- 需要确认模式：N 条
- 连续异常熔断阈值：N 次

### 最近 24h 操作摘要
| 时间 | 操作 | 目标 | 结果 |
|------|------|------|------|

### 风险等级
[🟢 安全 / 🟡 注意 / 🔴 风险]
```
