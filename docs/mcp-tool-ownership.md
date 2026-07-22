# MCP 工具归属表

> 建立日期: 2026-07-22
> 目的: 列出每个工具的当前归属、读写类型、安全机制和未来归属计划，为 Gateway 迁移提供依据。

---

## 图例

| 列 | 含义 |
|----|------|
| 工具名称 | MCP 工具名 (tia-mcp 使用函数名, plc-mcp-bridge 使用 name 参数) |
| 当前 MCP 服务器 | tia-mcp / plc-mcp-bridge |
| 读/写类型 | R=只读, W=变更, RW=两者 |
| Preview/Apply | 是否支持 preview 然后 apply 的模式 |
| 人工确认 | 是否需要 confirmation_token |
| 测试 | 是否有对应的单元测试 |
| 未来归属 | Gateway / tia-engine / adapter / 废弃 |

---

## 工具归属表

### tia-mcp 工具

| 工具名称 | 当前 MCP 服务器 | 读/写类型 | Preview/Apply | 人工确认 | 是否有测试 | 未来归属 | 备注 |
|----------|---------------|-----------|---------------|----------|-----------|----------|------|
| list_devices | tia-mcp | R | 否 | 否 | 否 | Gateway | 与 plc_list_devices 重复 |
| import_scl_file | tia-mcp | W | 否 | 否 (安全链) | 否 | Gateway | 含 lint 和 safety_gate |
| create_plc_tags | tia-mcp | W | 否 | 否 | 否 | Gateway | 批量创建，与 plc_add_tag 粒度不同 |
| compile_project | tia-mcp | W | 否 | 否 | 否 | Gateway | 与 plc_compile_project 重复 |
| list_blocks | tia-mcp | R | 否 | 否 | 否 | Gateway | 与 plc_list_blocks 重复 |
| create_block | tia-mcp | W | 否 | 否 (安全链) | 否 | Gateway | 与 plc_create_block 重复 |
| export_block | tia-mcp | R | 否 | 否 | 否 | Gateway | 与 plc_export_block 重复 |
| list_udts | tia-mcp | R | 否 | 否 | 否 | Gateway | 与 plc_list_udts 重复 |
| go_online | tia-mcp | W | 否 | 否 | 否 | Gateway | 与 plc_go_online 重复 |
| go_offline | tia-mcp | W | 否 | 否 | 否 | Gateway | 与 plc_go_offline 重复 |
| download_to_plcsim | tia-mcp | W | 否 | 否 (安全链) | 否 | Gateway | 与 plc_download_project 重复 |
| generate_scl_code | tia-mcp | R | 否 | 否 | 否 | tia-engine | AI 生成，需 DeepSeek |
| generate_and_import | tia-mcp | W | 否 | 否 (安全链) | 否 | tia-engine | 组合操作 |
| create_ladder_block | tia-mcp | W | 否 | 否 (安全链) | 否 | tia-engine | 需 CartGen 和 DeepSeek |
| call_fb_in_ob1 | tia-mcp | W | 否 | 否 (安全链) | 否 | tia-engine | OB1 自动化 |
| full_pipeline | tia-mcp | W | 否 | 否 (安全链) | 否 | tia-engine | 端到端流水线 |

### plc-mcp-bridge 工具 (TiaWorker 委托)

| 工具名称 | 当前 MCP 服务器 | 读/写类型 | Preview/Apply | 人工确认 | 是否有测试 | 未来归属 | 备注 |
|----------|---------------|-----------|---------------|----------|-----------|----------|------|
| plc_list_blocks | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_list_dbs | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_create_block | plc-mcp-bridge | W | 是 | 否 | 是 | Gateway |  |
| plc_export_block | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_import_block | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_get_block_details | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_delete_block | plc-mcp-bridge | W | 是 | 否 | 是 | Gateway |  |
| plc_compile_block | plc-mcp-bridge | W | 否 | 否 | 是 | Gateway |  |
| plc_create_db | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_delete_db | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_get_block_interface | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_list_tag_tables | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_get_tags | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_add_tag | plc-mcp-bridge | W | 是 | 否 | 是 | Gateway |  |
| plc_create_tag_table | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_delete_tag_table | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_search_tags | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_check_tag_conflicts | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_find_free_address | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_delete_tag | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_list_udts | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_create_udt | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_delete_udt | plc-mcp-bridge | W | 是 | 否 | 否 | Gateway |  |
| plc_list_watch_tables | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_create_watch_table | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_delete_watch_table | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_compile_project | plc-mcp-bridge | W | 否 | 否 | 是 | Gateway |  |
| plc_list_devices | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_save_project | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_get_project_info | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_create_project | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_archive_project | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_close_project | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_list_backups | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_get_hardware_info | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_find_unused_blocks | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_find_callers | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_get_compiler_errors | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_check_consistency | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway |  |
| plc_export_all_xml | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_export_tags_csv | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_get_status_info | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_go_online | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_go_offline | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_get_device_config | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_get_rack_slot | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_download_project | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_fio_write_config | plc-mcp-bridge | W | 否 | 否 | 否 | adapter | Factory I/O 适配 |
| plc_fio_launch | plc-mcp-bridge | W | 否 | 否 | 否 | adapter | Factory I/O 适配 |
| plc_run_pipeline | plc-mcp-bridge | W | 否 | 否 | 否 | tia-engine | 端到端流水线 |
| plc_golden_restore | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway |  |
| plc_get_config | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway |  |
| plc_list_instances | plc-mcp-bridge | R | 否 | 否 | 是 | Gateway | PLCSIM 管理 |
| plc_create_instance | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_stop_instance | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_get_state | plc-mcp-bridge | R | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_restore_from_golden | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_archive_to_golden | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_switch_to_tcpip | plc-mcp-bridge | W | 否 | 否 | 否 | Gateway | PLCSIM 管理 |
| plc_apply | plc-mcp-bridge | W | 是 (核心) | 否 | 否 | Gateway | Preview-Apply 核心 |
| s7_connect | plc-mcp-bridge | W | 否 | 否 | 否 | adapter | S7 协议适配 |
| s7_disconnect | plc-mcp-bridge | W | 否 | 否 | 否 | adapter | S7 协议适配 |
| s7_read | plc-mcp-bridge | R | 否 | 否 | 否 | adapter | S7 协议适配 |
| s7_write | plc-mcp-bridge | W | 否 | 是 | 否 | adapter | S7 协议适配 |
| s7_status | plc-mcp-bridge | R | 否 | 否 | 否 | adapter | S7 协议适配 |

---

## 未来归属说明

| 归属 | 含义 | 包含范围 |
|------|------|----------|
| Gateway | 统一 PLC Engineering Gateway 核心 | 项目/块/标签/UDT/Watch/硬件/编译/诊断/在线/下载/PLCSIM 等 TIA Openness 操作 |
| tia-engine | AI 工程引擎层 (需 DeepSeek/CartGen) | SCL 生成、梯形图生成、全流程自动化 |
| adapter | 协议适配器层 | S7 运行时通信、Factory I/O 等第三方集成 |
| 废弃 | 将被替代或移除 | 重复工具中功能较弱的版本 |
