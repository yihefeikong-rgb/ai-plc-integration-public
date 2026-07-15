# Handoff — AI 接入 PLC

> 用途：每次会话结束时填写，作为下一次会话的第一份上下文。
> 
> 推荐读取顺序：`handoff.md` → `task_plan.md` → `progress.md` → `findings.md` → `decisions.md`

---

## 最新 Handoff

### 2026-07-15：Pipeline 元数据与 MCP 凭据首批重构完成

- **本次完成**：
  - 修复后端注入 `authenticated_operator` 后 `nl_to_plcsim_pipeline` 在第 0 步拒参的问题；安全 actor 已从业务 input 分离为执行元数据。
  - 为 TIA、OPC UA、Modbus、三菱和 Robot MCP 建立 adapter 内部凭据注入、调用方覆盖拒绝、缺失失败关闭和 stdio 子进程环境透传。
  - Robot MCP 的认证默认值与 `MCP_AUTH_TOKEN` 对齐。
  - 补齐凭据快照、异常脱敏、取消清理，以及 adapter 内与连接池跨实例的 connect/disconnect 并发生命周期测试。
- **当前状态**：
  - 分支：`codex/phase2a-pipeline-auth`
  - 改动未暂存、未提交、未推送。
  - 根默认离线 `338 passed / 41 deselected`；后端 `286 passed`；前端 `2 passed`；Robot 模拟后端 `23 passed`。
  - Task 1、Task 2 的规格与代码质量审查均为 APPROVED；首次集成审查发现并阻断连接池跨实例竞态，修复后的最终复审为 APPROVED。
- **证据边界**：
  - 未启动真实 MCP/TIA/PLCSIM/Factory I/O；不能据此宣称项目已加载、下载完成、CPU RUN 或 PLC 可读。
- **下一步**：
  - 先由人工决定是否保留/提交本分支改动。
  - 后续确认令牌、目标身份和 Robot 假成功问题必须另立计划与授权，不得从本阶段自动续跑。
- **详细结果**：
  - `.plans/ai-plc-integration/refactor_phase2a_red_test_results.md`

### 2026-07-04：Bridge 目标模式计划 C-14.2 ~ C-19 收口

- **本次完成**：
  - `C-14.2` 会话级工作目录绑定：`ws_task_runner.py` 创建 session 时发送项目根 `workDir`
  - `C-14.3` 会话复用：默认复用 `state.json.session_id`，避免每轮新开 cc-haha/Claude 对话
  - `C-15` 稳定化：完成 5 轮低风险协作层真实运行验证，修复同秒 `run_id` 覆盖问题
  - `C-16` 权限分级：项目根内只读白名单，写入/命令/未知/畸形输入默认拒绝
  - `C-17` Codex Review 草案：`codex_review_draft.py` 生成 `PASS DRAFT` / `CONDITIONAL PASS DRAFT` / `BLOCK DRAFT`
  - `C-18` Stop Rule：统一记录 `NONE` / `PERMISSION_DENIED` 等停止原因到 `claude_result.md` 和 `state.json`
  - `C-19` 监督式连续运行门控：`supervised_batch.py` 只做 dry-run 门控和下一条命令建议，不自动执行、不循环
  - 人工确认记录器：`ack_review.py` 显式记录 PASS/BLOCK，写入 `next_action.md`，不执行后续任务
- **当前状态**：
  - `bridge/state.json`：`stage=DONE`、`review_status=PASS`、`stop_rule=NONE`
  - 当前复用 session：`f2d515a0-74b6-44c2-8337-13d6faae4214`
  - C-19 示例队列 2 条任务均已确认完成，`supervised_batch.py` 返回 `ALL_TASKS_DONE`
  - 未启用 hooks、自动轮询、无人值守循环、自动 git、自动权限批准
- **验证命令**：
  - `D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_ws_task_runner.py`
  - `D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_codex_review_draft.py`
  - `D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_supervised_batch.py`
  - `D:/Python3/python.exe .plans/ai-plc-integration/bridge/test_ack_review.py`
- **下一步任务**：
  - [ ] 若继续 C-19，人工先向 `bridge/templates/supervised-tasks.example.txt` 或新的队列文件追加低风险任务
  - [ ] 执行新任务时必须继续复用同一个 `session_id`
  - [ ] 如要进入更高自动化级别，需先明确新的计划和人工确认边界
- **注意事项**：
  - `Read` 在真实 cc-haha 会话中通常不会触发 `permission_request`，只读 ALLOW 分支主要由单元测试覆盖
  - `PERMISSION_DENIED` 已用真实写入探针验证：写入未落盘，Stop Rule 正确记录
  - `git status` 可能出现用户级 `C:\Users\huangxinyang/.config/git/ignore` 权限警告，不影响 bridge 测试

### 2026-06-23：Bridge v1 与早期项目交接记录

- **日期**：2026-06-23
- **本次完成**：
  - **协作层 Phase 1 完成**：落地 `.ccb/`、`bridge/`、Agent 协议、状态模板和人工闭环规则
  - **手动闭环演示完成**：跑通 `task_packet.md → claude_result.md → codex_review.md → next_action.md → DONE`
  - **Phase 2A 完成**：确认协作层文件建议纳入 Git，验证 `.gitignore` 不会误忽略 `.ccb/` 与 `bridge/`
  - **Phase 2B 完成**：在 `bridge/README.md` 固化“协作层文件纳入 Git 的说明”
  - **Phase 3A 完成**：新增 `runner_dry_run.py` + `runner_readme.md`，只读 `state.json`、stdout 输出、支持停止态
  - **Phase 4 完成**：基于真实低风险任务验证 `Codex → Claude Code → Codex Review → DONE` 完整闭环
  - **Phase 5 完成**：新增 `runner_step.py`，支持受控单步 `--execute`，保留 dry-run 边界
  - **Phase 5 安全返工完成**：移除 `shell=True`，改为 `shlex.split(cmd)` + `subprocess.run(argv, shell=False)`
  - **Phase 5.1B 完成**：新增 `runner_step.py --copy`，兼容 cc-haha 桌面版，将 prompt 复制到 Windows 剪贴板
  - **当前 bridge 能力**：
    - `runner_dry_run.py`：只读状态，输出下一步建议
    - `runner_step.py --execute`：受控单步 CLI 调用，需 `YES` 确认
    - `runner_step.py --copy`：剪贴板兼容模式，适配 cc-haha GUI
  - **历史记录保留**：
  - **落地优化方案制定**：基于 `软件/` 参考资料的代码行为分析，识别 10 个缺陷（D-01~D-10），制定 4 阶段落地优化方案
  - **Agent 模型分配修正**：项目级 Agent 按职责分级（team-lead=Flash, developer=Sonnet, reviewer=Opus, researcher=Sonnet, documenter=Haiku），写入 claude.md + 5 个 agent 文件
  - **T021 修复 pipeline 阻断 bug**：D-09 数据契约统一、D-02 import-scl-replace 命令、D-03 BOM 防御 → 审查 STRONG
  - **T022 SCL 规范注入 + 静态校验器**：`_rules.md` 17 条铁律、`scl_lint.py` 6 条检查规则、规范注入 AI 提示词、lint 集成 → 审查 STRONG
  - **T023 编译错误结构化 + AI 重试循环**：TiaWorker compile 返回结构化 error_list、pipeline 3 次 AI 重试、markdown 格式兼容 → 审查 CONDITIONAL PASS
  - **T024 多块依赖顺序工作流**：`tia_multi_block_pipeline` UDT→DB→FC/FB/OB 顺序导入 → 审查 STRONG
  - **T025 真实环境冒烟脚本**：`scripts/e2e_smoke.py` + `scripts/preflight.py` + `scripts/demo.py`
  - **T026 一键启动 + Demo 文档**：`start.bat` + `docs/quickstart-落地版.md`
  - **敏感信息清理**：`软件/` 目录含真实 API Key，已加入 `.gitignore`
- **当前状态**：
  - 协作层：Phase 1~5.1B 已完成，Bridge v1 验证通过
  - 闭环方式：人工闭环 + dry-run runner + 受控单步 execute + GUI 兼容 copy
  - 自动化：未启用 hooks、orchestrator、无人值守、自动锁、自动循环
  - CLI 安全边界：`runner_step.py` 已移除 `shell=True`，停止态拒绝执行
  - GUI 兼容：cc-haha 桌面版当前推荐 `runner_step.py --copy`，不强推 `CLAUDE_CODE_CMD` 真实调用
  - 编排层：5 服务器已连接，所有 pipeline 阻断 bug 已修复
  - SCL 质量：双轨防护（AI 规范注入 + scl_lint 静态校验）
  - 编译重试：3 次 AI 自修复循环
  - 多块依赖：UDT→DB→FC/FB/OB 顺序导入工作流
  - 冒烟脚本 + 一键启动 + 文档：全部就绪
  - 任务队列：T021-T026 全部 DONE
- **下一步任务**：
  - [ ] 人工决定是否继续推进 Bridge v2（例如模板/运行态拆分、提交前清单、更多 GUI 兼容）
  - [ ] 如继续推进，先创建新的 `task_packet.md`，不要自动续跑
  - [ ] 在真实 TIA V21 + PLCSIM Advanced 环境跑 `python scripts/demo.py` 验证最小闭环
  - [ ] Factory I/O 可视化集成
  - [ ] RBAC 安全网关
- **阻塞/风险**：
  - `cc-haha` 当前为桌面安装版，不是源码 CLI 形态；GUI 使用推荐 `--copy`，CLI execute 仍需谨慎配置 `CLAUDE_CODE_CMD`
  - `bridge/` 运行态文件当前仍在版本控制范围内，后续如污染增多应拆分 `templates/` 与 `runs/`
- **注意事项**：
  - `软件/` 目录已在 `.gitignore` 中排除（含真实 DeepSeek API Key）
  - scl_lint 是静态校验（正则），不能替代 TIA 编译检查
  - Opus 模型当前映射为 GLM-5.2
  - `_rules.md` 位置：`plc-code-templates/siemens-scl/_rules.md`
  - 文档内统一使用 `CLAUDE.md` 表述，Windows 文件系统中实际文件名保持 `claude.md`
  - `bridge/state.json` 当前应处于 `DONE / owner=human / review_status=PASS`（Phase 5.1B 完成态）

---

## Handoff 模板

```markdown
- **日期**：YYYY-MM-DD
- **本次完成**：
  - 
- **当前状态**：
  - 
- **下一步任务**：
  - [ ] 
- **阻塞/风险**：
  - 
- **相关文件**：
  - 
- **注意事项**：
  - 
```

---

## 历史 Handoff

_暂无_
