# MCP 迁移映射表

> 建立日期: 2026-07-22
> 目的: 规划从当前 tia-mcp + plc-mcp-bridge 双服务器架构到统一 PLC Engineering Gateway 的工具迁移路径。

---

## 迁移批次说明

| 批次 | 名称 | 时间 | 范围 |
|------|------|------|------|
| Batch 1 | 核心基建 | 第 1-2 周 | 项目管理、编译、一致性检查、只读查询 |
| Batch 2 | 工程操作 | 第 3-4 周 | 块/标签/UDT/Watch 表的 CRUD |
| Batch 3 | AI 工程态 | 第 5-6 周 | SCL 生成、梯形图生成、全流程自动化 |
| Batch 4 | 运行时通信 | 第 7-8 周 | S7 协议、Factory I/O 适配器 |
| Batch 5 | 废弃与清理 | 第 9 周 | 删除旧服务器、更新文档 |

---

## 兼容层策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 直通 (Pass-through) | Gateway 直接转发到 TiaWorker | 已有 TiaWorker 命令的简单操作 |
| 适配器 (Adapter) | Gateway 调用独立 Python 模块 | S7 协议、Factory I/O 等非 TIA 操作 |
| 包装 (Wrapper) | Gateway 包装 tia-mcp 原有逻辑 | AI 生成、LadderSpec 等复杂操作 |
| 代理 (Proxy) | Gateway 委托给旧 MCP 服务器 | 过渡期兼容旧客户端 |
| 合并 (Merge) | 合并两个重复工具为一个 | 当前重复的 9 个工具 |

---

## 迁移映射表

### Batch 1: 核心基建 (第 1-2 周)

| 当前工具路径 | 来源 | 目标工具路径 (Gateway) | 迁移批次 | 兼容层策略 | 备注 |
|-------------|------|----------------------|----------|-----------|------|
| tia-mcp: list_devices | tia-mcp | gateway.list_devices | Batch 1 | 合并 | 合并 plc_list_devices |
| bridge: plc_list_devices | plc-mcp-bridge | gateway.list_devices | Batch 1 | 合并 | 统一接口签名 |
| bridge: plc_get_project_info | plc-mcp-bridge | gateway.get_project_info | Batch 1 | 直通 |  |
| bridge: plc_save_project | plc-mcp-bridge | gateway.save_project | Batch 1 | 直通 |  |
| bridge: plc_create_project | plc-mcp-bridge | gateway.create_project | Batch 1 | 直通 |  |
| bridge: plc_archive_project | plc-mcp-bridge | gateway.archive_project | Batch 1 | 直通 |  |
| bridge: plc_close_project | plc-mcp-bridge | gateway.close_project | Batch 1 | 直通 |  |
| bridge: plc_list_backups | plc-mcp-bridge | gateway.list_backups | Batch 1 | 直通 |  |
| bridge: plc_get_config | plc-mcp-bridge | gateway.get_config | Batch 1 | 直通 |  |
| tia-mcp: compile_project | tia-mcp | gateway.compile_project | Batch 1 | 合并 | 合并 plc_compile_project |
| bridge: plc_compile_project | plc-mcp-bridge | gateway.compile_project | Batch 1 | 合并 |  |
| bridge: plc_get_compiler_errors | plc-mcp-bridge | gateway.get_compiler_errors | Batch 1 | 直通 |  |
| bridge: plc_check_consistency | plc-mcp-bridge | gateway.check_consistency | Batch 1 | 直通 |  |
| bridge: plc_get_hardware_info | plc-mcp-bridge | gateway.get_hardware_info | Batch 1 | 直通 |  |
| bridge: plc_get_device_config | plc-mcp-bridge | gateway.get_device_config | Batch 1 | 直通 |  |
| bridge: plc_get_rack_slot | plc-mcp-bridge | gateway.get_rack_slot | Batch 1 | 直通 |  |
| bridge: plc_find_unused_blocks | plc-mcp-bridge | gateway.find_unused_blocks | Batch 1 | 直通 |  |
| bridge: plc_find_callers | plc-mcp-bridge | gateway.find_callers | Batch 1 | 直通 |  |
| bridge: plc_get_status_info | plc-mcp-bridge | gateway.get_plc_status | Batch 1 | 直通 |  |
| bridge: plc_export_all_xml | plc-mcp-bridge | gateway.export_all_xml | Batch 1 | 直通 |  |
| bridge: plc_export_tags_csv | plc-mcp-bridge | gateway.export_tags_csv | Batch 1 | 直通 |  |
### Batch 2: 工程操作 (第 3-4 周)

| 当前工具路径 | 来源 | 目标工具路径 (Gateway) | 迁移批次 | 兼容层策略 | 备注 |
|-------------|------|----------------------|----------|-----------|------|
| tia-mcp: list_blocks | tia-mcp | gateway.list_blocks | Batch 2 | 合并 | 合并 plc_list_blocks |
| bridge: plc_list_blocks | plc-mcp-bridge | gateway.list_blocks | Batch 2 | 合并 | 保留类型过滤 |
| bridge: plc_list_dbs | plc-mcp-bridge | gateway.list_dbs | Batch 2 | 直通 |  |
| tia-mcp: create_block | tia-mcp | gateway.create_block | Batch 2 | 合并 | 合并 plc_create_block |
| bridge: plc_create_block | plc-mcp-bridge | gateway.create_block | Batch 2 | 合并 | 保留 preview/block_number |
| bridge: plc_create_db | plc-mcp-bridge | gateway.create_db | Batch 2 | 直通 |  |
| bridge: plc_delete_block | plc-mcp-bridge | gateway.delete_block | Batch 2 | 直通 |  |
| bridge: plc_delete_db | plc-mcp-bridge | gateway.delete_db | Batch 2 | 直通 |  |
| tia-mcp: export_block | tia-mcp | gateway.export_block | Batch 2 | 合并 | 合并 plc_export_block |
| bridge: plc_export_block | plc-mcp-bridge | gateway.export_block | Batch 2 | 合并 | 保留 output_path |
| bridge: plc_import_block | plc-mcp-bridge | gateway.import_block | Batch 2 | 直通 |  |
| bridge: plc_get_block_details | plc-mcp-bridge | gateway.get_block_details | Batch 2 | 直通 |  |
| bridge: plc_get_block_interface | plc-mcp-bridge | gateway.get_block_interface | Batch 2 | 直通 |  |
| bridge: plc_compile_block | plc-mcp-bridge | gateway.compile_block | Batch 2 | 直通 |  |
| tia-mcp: import_scl_file | tia-mcp | gateway.import_scl | Batch 2 | 包装 | 保留 lint 和 safety_gate |
| tia-mcp: list_udts | tia-mcp | gateway.list_udts | Batch 2 | 合并 | 合并 plc_list_udts |
| bridge: plc_list_udts | plc-mcp-bridge | gateway.list_udts | Batch 2 | 合并 |  |
| bridge: plc_create_udt | plc-mcp-bridge | gateway.create_udt | Batch 2 | 直通 |  |
| bridge: plc_delete_udt | plc-mcp-bridge | gateway.delete_udt | Batch 2 | 直通 |  |
| bridge: plc_list_watch_tables | plc-mcp-bridge | gateway.list_watch_tables | Batch 2 | 直通 |  |
| bridge: plc_create_watch_table | plc-mcp-bridge | gateway.create_watch_table | Batch 2 | 直通 |  |
| bridge: plc_delete_watch_table | plc-mcp-bridge | gateway.delete_watch_table | Batch 2 | 直通 |  |
| tia-mcp: create_plc_tags | tia-mcp | gateway.create_tags | Batch 2 | 包装 | 批量创建 |
| bridge: plc_list_tag_tables | plc-mcp-bridge | gateway.list_tag_tables | Batch 2 | 直通 |  |
| bridge: plc_get_tags | plc-mcp-bridge | gateway.get_tags | Batch 2 | 直通 |  |
| bridge: plc_add_tag | plc-mcp-bridge | gateway.add_tag | Batch 2 | 直通 | 保留 preview |
| bridge: plc_create_tag_table | plc-mcp-bridge | gateway.create_tag_table | Batch 2 | 直通 |  |
| bridge: plc_delete_tag_table | plc-mcp-bridge | gateway.delete_tag_table | Batch 2 | 直通 |  |
| bridge: plc_delete_tag | plc-mcp-bridge | gateway.delete_tag | Batch 2 | 直通 |  |
| bridge: plc_search_tags | plc-mcp-bridge | gateway.search_tags | Batch 2 | 直通 |  |
| bridge: plc_check_tag_conflicts | plc-mcp-bridge | gateway.check_tag_conflicts | Batch 2 | 直通 |  |
| bridge: plc_find_free_address | plc-mcp-bridge | gateway.find_free_address | Batch 2 | 直通 |  |
| tia-mcp: go_online | tia-mcp | gateway.go_online | Batch 2 | 合并 | 合并 plc_go_online |
| bridge: plc_go_online | plc-mcp-bridge | gateway.go_online | Batch 2 | 合并 | 保留 dry_run |
| tia-mcp: go_offline | tia-mcp | gateway.go_offline | Batch 2 | 合并 | 合并 plc_go_offline |
| bridge: plc_go_offline | plc-mcp-bridge | gateway.go_offline | Batch 2 | 合并 | 保留 dry_run |
| tia-mcp: download_to_plcsim | tia-mcp | gateway.download_project | Batch 2 | 合并 | 合并 plc_download_project |
| bridge: plc_download_project | plc-mcp-bridge | gateway.download_project | Batch 2 | 合并 | 保留 golden-restore |
| bridge: plc_golden_restore | plc-mcp-bridge | gateway.golden_restore | Batch 2 | 直通 |  |
| bridge: plc_apply | plc-mcp-bridge | gateway.apply | Batch 2 | 直通 | Preview-Apply 核心 |
### Batch 3: AI 工程态 (第 5-6 周)

| 当前工具路径 | 来源 | 目标工具路径 (Gateway) | 迁移批次 | 兼容层策略 | 备注 |
|-------------|------|----------------------|----------|-----------|------|
| tia-mcp: generate_scl_code | tia-mcp | tia-engine.generate_scl | Batch 3 | 包装 | 需 DeepSeek API |
| tia-mcp: generate_and_import | tia-mcp | tia-engine.generate_and_import | Batch 3 | 包装 | 组合操作 |
| tia-mcp: create_ladder_block | tia-mcp | tia-engine.create_ladder | Batch 3 | 包装 | 需 CartGen + DeepSeek |
| tia-mcp: call_fb_in_ob1 | tia-mcp | tia-engine.call_fb_in_ob1 | Batch 3 | 包装 | OB1 自动化 |
| tia-mcp: full_pipeline | tia-mcp | tia-engine.full_pipeline | Batch 3 | 包装 | 端到端流水线 |
| bridge: plc_run_pipeline | plc-mcp-bridge | tia-engine.run_pipeline | Batch 3 | 包装 | P3 流水线 |

### Batch 4: 运行时通信 (第 7-8 周)

| 当前工具路径 | 来源 | 目标工具路径 (Gateway) | 迁移批次 | 兼容层策略 | 备注 |
|-------------|------|----------------------|----------|-----------|------|
| bridge: s7_connect | plc-mcp-bridge | adapter.s7.connect | Batch 4 | 适配器 | S7 协议 |
| bridge: s7_disconnect | plc-mcp-bridge | adapter.s7.disconnect | Batch 4 | 适配器 |  |
| bridge: s7_read | plc-mcp-bridge | adapter.s7.read | Batch 4 | 适配器 |  |
| bridge: s7_write | plc-mcp-bridge | adapter.s7.write | Batch 4 | 适配器 | 保留 confirmation |
| bridge: s7_status | plc-mcp-bridge | adapter.s7.status | Batch 4 | 适配器 |  |
| bridge: plc_fio_write_config | plc-mcp-bridge | adapter.fio.write_config | Batch 4 | 适配器 | Factory I/O |
| bridge: plc_fio_launch | plc-mcp-bridge | adapter.fio.launch | Batch 4 | 适配器 |  |
| bridge: plc_list_instances | plc-mcp-bridge | gateway.plcsim.list_instances | Batch 4 | 直通 | PLCSIM 管理 |
| bridge: plc_create_instance | plc-mcp-bridge | gateway.plcsim.create_instance | Batch 4 | 直通 |  |
| bridge: plc_stop_instance | plc-mcp-bridge | gateway.plcsim.stop_instance | Batch 4 | 直通 |  |
| bridge: plc_get_state | plc-mcp-bridge | gateway.plcsim.get_state | Batch 4 | 直通 |  |
| bridge: plc_restore_from_golden | plc-mcp-bridge | gateway.plcsim.restore_from_golden | Batch 4 | 直通 |  |
| bridge: plc_archive_to_golden | plc-mcp-bridge | gateway.plcsim.archive_to_golden | Batch 4 | 直通 |  |
| bridge: plc_switch_to_tcpip | plc-mcp-bridge | gateway.plcsim.switch_to_tcpip | Batch 4 | 直通 |  |
### Batch 5: 废弃与清理 (第 9 周)

| 当前工具路径 | 来源 | 目标工具路径 (Gateway) | 迁移批次 | 兼容层策略 | 备注 |
|-------------|------|----------------------|----------|-----------|------|
| tia-mcp: 全部工具 | tia-mcp | -- | Batch 5 | 代理 -> 废弃 | 等所有工具迁移到 Gateway 后停用 |
| bridge: 全部工具 (旧名) | plc-mcp-bridge | -- | Batch 5 | 代理 -> 废弃 | 旧工具名保留兼容别名后移除 |

---

## 兼容性保障

### 旧名兼容别名

迁移后，以下旧工具名应保留为 Gateway 的兼容别名，持续至少 2 个版本:

| 旧工具名 | 新工具名 | 保留期限 |
|----------|---------|----------|
| plc_list_devices | gateway.list_devices | 2 个版本 |
| plc_list_blocks | gateway.list_blocks | 2 个版本 |
| plc_create_block | gateway.create_block | 2 个版本 |
| plc_export_block | gateway.export_block | 2 个版本 |
| plc_list_udts | gateway.list_udts | 2 个版本 |
| plc_compile_project | gateway.compile_project | 2 个版本 |
| plc_go_online | gateway.go_online | 2 个版本 |
| plc_go_offline | gateway.go_offline | 2 个版本 |
| plc_download_project | gateway.download_project | 2 个版本 |
| import_scl_file | gateway.import_scl | 2 个版本 |
| list_devices | gateway.list_devices | 2 个版本 |
| s7_connect | adapter.s7.connect | 2 个版本 |

### 认证迁移

| 当前方式 | 目标方式 | 迁移说明 |
|---------|---------|----------|
| tia-mcp: auth_token 参数 | Gateway: JWT 令牌 | 统一认证机制 |
| bridge: 无认证 | Gateway: JWT 令牌 | 新增认证 |

### 安全机制迁移

| 当前方式 | 目标方式 | 迁移说明 |
|---------|---------|----------|
| tia-mcp: safety_gate | Gateway: 统一安全链 | 保留 safety_gate + audit |
| bridge: preview-apply | Gateway: 统一 preview-apply | 扩展 preview 到所有 W 操作 |
| bridge: s7 confirmation_token | Gateway: 统一确认服务 | 保留人工确认机制 |
