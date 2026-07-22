# MCP 能力矩阵表

> 建立日期: 2026-07-22
> 目的: 记录 tia-mcp、plc-mcp-bridge、TiaWorker 三者的当前能力基线，为后续收敛到统一 PLC Engineering Gateway 提供参考。

---

## 图例

| 符号 | 含义 |
|------|------|
| Y | 支持 |
| P | 部分支持 |
| N | 不支持 |
| - | 不适用 |
| L0 | 无安全措施 |
| L1 | 只读操作 (readOnlyHint) |
| L2 | 变更操作带 dry-run / preview |
| L3 | 变更操作需人工确认 (confirmation_token) |
| L4 | 变更操作需安全链校验 (safety_gate + audit) |

---

## 1. 功能领域总览

### 1.1 项目管理

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 创建项目 | N | plc_create_project | create-project | 仅 bridge | L2 |
| 列出设备 | list_devices | plc_list_devices | list-devices | **重复** | L1 |
| 获取项目信息 | N | plc_get_project_info | get-project-info | 仅 bridge | L1 |
| 保存项目 | N | plc_save_project | save-project | 仅 bridge | L2 |
| 归档项目 (ZAP) | N | plc_archive_project | archive-project | 仅 bridge | L2 |
| 关闭项目 | N | plc_close_project | close-project | 仅 bridge | L4 |
| 列出备份 | N | plc_list_backups | list-backups | 仅 bridge | L1 |
| 获取配置 | N | plc_get_config | -- | 仅 bridge | L1 |
### 1.2 块管理 (FB/FC/OB/DB)

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 列出块 | list_blocks | plc_list_blocks | list-blocks | **重复** | L1 |
| 列出 DB | N | plc_list_dbs | list-dbs | 仅 bridge | L1 |
| 创建块 | create_block | plc_create_block | create-block | **重复** | L4 |
| 创建 DB | N | plc_create_db | create-db | 仅 bridge | L2 |
| 删除块 | N | plc_delete_block | delete-block | 仅 bridge | L4 |
| 删除 DB | N | plc_delete_db | delete-db | 仅 bridge | L4 |
| 导出块 | export_block | plc_export_block | export-block | **重复** | L1 |
| 导入块 (XML) | N | plc_import_block | import-block | 仅 bridge | L4 |
| 获取块详情 | N | plc_get_block_details | get-block-details | 仅 bridge | L1 |
| 获取块接口 | N | plc_get_block_interface | get-block-interface | 仅 bridge | L1 |
| 编译单个块 | N | plc_compile_block | compile-block | 仅 bridge | L2 |
| 导出全部 XML | N | plc_export_all_xml | export-all-xml | 仅 bridge | L1 |
| 导入 SCL 文件 | import_scl_file | -- | import-scl | 仅 tia-mcp | L4 |
| AI 生成 SCL | generate_scl_code | -- | -- | 仅 tia-mcp | L1 |
| AI 生成+导入 | generate_and_import | -- | -- | 仅 tia-mcp | L4 |
| 创建梯形图 | create_ladder_block | -- | -- | 仅 tia-mcp | L4 |
| 一键全流程 | full_pipeline | -- | -- | 仅 tia-mcp | L4 |
| OB1 调用链 | call_fb_in_ob1 | -- | -- | 仅 tia-mcp | L4 |
### 1.3 标签管理

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 列出标签表 | N | plc_list_tag_tables | list-tags | 仅 bridge | L1 |
| 获取标签 | N | plc_get_tags | get-tags | 仅 bridge | L1 |
| 添加标签 | create_plc_tags | plc_add_tag | add-tag | **部分重复** | L2 |
| 创建标签表 | N | plc_create_tag_table | create-tag-table | 仅 bridge | L2 |
| 删除标签表 | N | plc_delete_tag_table | delete-tag-table | 仅 bridge | L4 |
| 删除标签 | N | plc_delete_tag | delete-tag | 仅 bridge | L4 |
| 搜索标签 | N | plc_search_tags | search-tag | 仅 bridge | L1 |
| 检测地址冲突 | N | plc_check_tag_conflicts | check-tag-conflicts | 仅 bridge | L1 |
| 查找空闲地址 | N | plc_find_free_address | find-free-address | 仅 bridge | L1 |
| 导出标签 CSV | N | plc_export_tags_csv | export-tags-csv | 仅 bridge | L1 |
| 批量创建标签 | create_plc_tags (tags_json) | -- | -- | 仅 tia-mcp | L2 |

### 1.4 UDT 管理

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 列出 UDT | list_udts | plc_list_udts | list-udts | **重复** | L1 |
| 创建 UDT | N | plc_create_udt | create-udt | 仅 bridge | L2 |
| 删除 UDT | N | plc_delete_udt | delete-udt | 仅 bridge | L4 |

### 1.5 Watch 表管理

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 列出 Watch 表 | N | plc_list_watch_tables | list-watch-tables | 仅 bridge | L1 |
| 创建 Watch 表 | N | plc_create_watch_table | create-watch-table | 仅 bridge | L2 |
| 删除 Watch 表 | N | plc_delete_watch_table | delete-watch-table | 仅 bridge | L4 |

### 1.6 硬件配置

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 获取硬件信息 | N | plc_get_hardware_info | get-hardware-info | 仅 bridge | L1 |
| 获取设备配置 | N | plc_get_device_config | get-device-config | 仅 bridge | L1 |
| 获取机架/插槽 | N | plc_get_rack_slot | get-rack-slot | 仅 bridge | L1 |

### 1.7 编译

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 编译项目 | compile_project | plc_compile_project | compile | **重复** | L2 |
| 获取编译错误 | N | plc_get_compiler_errors | get-compiler-errors | 仅 bridge | L1 |
| 一致性检查 | N | plc_check_consistency | check-consistency | 仅 bridge | L1 |

### 1.8 诊断与交叉引用

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 查找未用块 | N | plc_find_unused_blocks | find-unused-blocks | 仅 bridge | L1 |
| 查找调用者 | N | plc_find_callers | find-callers | 仅 bridge | L1 |

### 1.9 在线/下载

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 在线连接 | go_online | plc_go_online | go-online | **重复** | L2 |
| 离线断开 | go_offline | plc_go_offline | go-offline | **重复** | L2 |
| 获取状态 | N | plc_get_status_info | get-plc-status | 仅 bridge | L1 |
| 下载到 PLCSIM | download_to_plcsim | plc_download_project | download | **重复** | L4 |
### 1.10 PLCSIM Advanced

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 列出实例 | N | plc_list_instances | -- | 仅 bridge | L1 |
| 创建实例 | N | plc_create_instance | -- | 仅 bridge | L2 |
| 停止实例 | N | plc_stop_instance | -- | 仅 bridge | L4 |
| 获取实例状态 | N | plc_get_state | -- | 仅 bridge | L1 |
| 从 golden 恢复 | N | plc_restore_from_golden | -- | 仅 bridge | L4 |
| 归档到 golden | N | plc_archive_to_golden | -- | 仅 bridge | L2 |
| 切换 TCP/IP | N | plc_switch_to_tcpip | -- | 仅 bridge | L4 |

### 1.11 S7 运行时通信

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| S7 连接 | N | s7_connect | -- | 仅 bridge | L2 |
| S7 断开 | N | s7_disconnect | -- | 仅 bridge | L2 |
| S7 读取 | N | s7_read | -- | 仅 bridge | L1 |
| S7 写入 | N | s7_write | -- | 仅 bridge | L4 |
| S7 状态 | N | s7_status | -- | 仅 bridge | L1 |

### 1.12 Factory I/O

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| 写入配置 | N | plc_fio_write_config | -- | 仅 bridge | L2 |
| 启动 FIO | N | plc_fio_launch | -- | 仅 bridge | L2 |
| 流水线 (P3) | N | plc_run_pipeline | -- | 仅 bridge | L4 |
| Golden 恢复 | N | plc_golden_restore | -- | 仅 bridge | L4 |

### 1.13 Preview-Apply 安全模式

| 功能 | tia-mcp | plc-mcp-bridge | TiaWorker | 是否重复 | 安全等级 |
|------|---------|----------------|-----------|----------|----------|
| Preview 操作 | N | 各工具 preview 参数 + plc_apply(token) | -- | 仅 bridge | L3 |
| 人工确认 | N | s7_write 内嵌 confirmation_token | -- | 仅 bridge | L3 |

---
## 2. 重复功能清单 (需合并)

以下工具在两个 MCP 服务器中同时存在，需要在 Gateway 中统一:

| 功能 | tia-mcp 工具名 | plc-mcp-bridge 工具名 | 差异说明 |
|------|---------------|----------------------|----------|
| 列出设备 | list_devices | plc_list_devices | 参数签名不同 |
| 列出块 | list_blocks | plc_list_blocks | bridge 支持类型过滤，返回格式不同 |
| 创建块 | create_block | plc_create_block | bridge 增加了 language/block_number/preview/dry_run |
| 导出块 | export_block | plc_export_block | bridge 增加 output_path 参数 |
| 列出 UDT | list_udts | plc_list_udts | 功能相同 |
| 编译项目 | compile_project | plc_compile_project | 功能相同 |
| 在线连接 | go_online | plc_go_online | bridge 增加 dry_run 参数 |
| 离线断开 | go_offline | plc_go_offline | bridge 增加 dry_run 参数 |
| 下载到 PLCSIM | download_to_plcsim | plc_download_project | 参数签名不同，bridge 增加 golden-restore 选项 |
| 添加标签 | create_plc_tags (批量) | plc_add_tag (单个) | 粒度不同 |

---
## 3. 缺失功能分析

### 3.1 tia-mcp 缺失 (相对于 plc-mcp-bridge)

- 项目管理: 创建/保存/归档/关闭/备份
- 块管理: 创建DB/删除块/导入XML/编译单个块/导出全部XML/块接口/块详情
- 标签管理: 列出标签表/搜索/地址冲突/空闲地址/删除标签/创建标签表
- UDT: 创建/删除
- Watch 表: 全部
- 硬件: 全部
- 诊断: 全部
- PLCSIM: 全部
- S7: 全部
- Factory I/O: 全部
- Preview-Apply: 全部

### 3.2 plc-mcp-bridge 缺失 (相对于 tia-mcp)

- SCL 导入 (带安全校验和 lint)
- AI 生成 SCL 代码
- AI 生成梯形图 (LadderSpec + CartGen)
- 一键全流程 (full_pipeline)
- OB1 调用链
- 批量创建标签 (仅支持单个添加)

### 3.3 两者均缺失

- OPC UA 通信
- Modbus 通信
- 三菱 PLC 支持
- 机器人支持 (如 KUKA, FANUC)
- 其他品牌 PLC 工程态支持

---
## 4. TiaWorker 命令清单 (底层引擎)

TiaWorker.exe 是 C# 编写的 TIA Openness 调用引擎，所有 MCP 工具最终通过 _run_tiaworker(command, ...) 委托给 TiaWorker。以下是 TiaWorker 支持的所有命令:

| 命令 | 所属领域 | 是否变更操作 | 说明 |
|------|----------|-------------|------|
| list-devices | 项目 | 否 | 列出 PLC 设备 |
| list-blocks | 块 | 否 | 列出程序块 |
| list-dbs | 块 | 否 | 列出数据块 |
| list-udts | UDT | 否 | 列出 UDT |
| list-tags | 标签 | 否 | 列出标签表 |
| list-watch-tables | Watch | 否 | 列出监控表 |
| list-backups | 项目 | 否 | 列出备份 |
| get-plc-status | 诊断 | 否 | 获取 PLC 状态 |
| get-project-info | 项目 | 否 | 获取项目信息 |
| get-block-details | 块 | 否 | 获取块详情 |
| get-block-interface | 块 | 否 | 获取块接口 |
| get-hardware-info | 硬件 | 否 | 获取硬件信息 |
| get-device-config | 硬件 | 否 | 获取设备配置 |
| get-rack-slot | 硬件 | 否 | 获取机架/插槽 |
| get-tags | 标签 | 否 | 获取标签 |
| get-compiler-errors | 编译 | 否 | 获取编译错误 |
| search-tag | 标签 | 否 | 搜索标签 |
| check-tag-conflicts | 标签 | 否 | 检查地址冲突 |
| find-free-address | 标签 | 否 | 查找空闲地址 |
| find-unused-blocks | 诊断 | 否 | 查找未用块 |
| find-callers | 诊断 | 否 | 查找调用者 |
| check-consistency | 编译 | 否 | 一致性检查 |
| export-block | 块 | 否 | 导出块 |
| export-all-xml | 块 | 否 | 全部导出 XML |
| export-tags-csv | 标签 | 否 | 导出 CSV |
| compile | 编译 | 是 | 编译项目 |
| compile-block | 编译 | 是 | 编译单个块 |
| create-block | 块 | 是 | 创建块 |
| create-db | 块 | 是 | 创建数据块 |
| create-udt | UDT | 是 | 创建 UDT |
| create-tag-table | 标签 | 是 | 创建标签表 |
| create-watch-table | Watch | 是 | 创建监控表 |
| create-project | 项目 | 是 | 创建项目 |
| delete-block | 块 | 是 | 删除块 |
| delete-db | 块 | 是 | 删除数据块 |
| delete-udt | UDT | 是 | 删除 UDT |
| delete-tag | 标签 | 是 | 删除标签 |
| delete-tag-table | 标签 | 是 | 删除标签表 |
| delete-watch-table | Watch | 是 | 删除监控表 |
| add-tag | 标签 | 是 | 添加标签 |
| import-scl | 块 | 是 | 导入 SCL 外部源 |
| import-scl-replace | 块 | 是 | 覆盖导入 SCL |
| import-block | 块 | 是 | 导入 XML 块 |
| save-project | 项目 | 是 | 保存项目 |
| archive-project | 项目 | 是 | 归档项目 |
| close-project | 项目 | 是 | 关闭项目 |
| go-online | 在线 | 是 | 在线连接 |
| go-offline | 在线 | 是 | 离线断开 |
| download | 下载 | 是 | 下载到 PLC |
| download-gui | 下载 | 是 | GUI 下载 |
| create-lad | 块 | 是 | 创建梯形图 (未使用) |

---
## 5. 统计摘要

| 统计项 | tia-mcp | plc-mcp-bridge | TiaWorker |
|--------|---------|----------------|-----------|
| MCP 工具数量 | 16 | 47 | -- |
| 其中只读工具 | 6 | 23 | ~30 (只读命令) |
| 其中变更工具 | 10 | 24 | ~20 (变更命令) |
| 重复工具 | -- | 9 (与 tia-mcp 重叠) | -- |
| 独立工具 | 7 (AI 生成/梯形图等) | 38 (PLCSIM/S7/FIO 等) | -- |
| 测试覆盖 | 无测试文件 | 有 (test_tools.py, test_s7.py 等) | -- |
| 安全等级 L4 | 8 个工具 | 12 个工具 | -- |
| 安全等级 L3 | 0 | 2 | -- |
| 安全等级 L2 | 1 | 17 | -- |
| 安全等级 L1 | 7 | 16 | -- |
