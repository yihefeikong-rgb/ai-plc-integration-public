// OrchestratorPanel 中文映射表与工具函数

export const WORKFLOW_CN = {
  s7_monitor: 'S7 监控',
  tia_full_pipeline: 'TIA 全流水线',
  robot_pick_place: '机器人取放',
  robot_monitor: '机器人监控',
  s7_safety_loop: 'S7 安全闭环',
}

export const CATEGORY_CN = {
  s7: 'S7 通信',
  tia: 'TIA 工程',
  safety: '安全',
  monitoring: '监控',
  control: '控制',
  engineering: '工程',
  desktop: '桌面',
  pipeline: '流水线',
  uncategorized: '未分类',
}

export const SERVER_CN = {
  'plc-mcp-bridge': 'PLC 桥接',
  'tia-mcp': 'TIA Portal',
  'opcua-mcp': 'OPC UA',
  'modbus-mcp': 'Modbus',
  'mitsubishi-mcp': '三菱',
  'robot-mcp': '机器人',
  'desktop-mcp': '桌面',
  'test-echo': '测试',
}

export const TOOL_CN = {
  // plc-mcp-bridge (65 工具)
  plc_add_tag: '添加标签', plc_apply: '应用配置', plc_archive_project: '归档项目',
  plc_archive_to_golden: '归档到模板', plc_check_consistency: '一致性检查',
  plc_check_tag_conflicts: '标签冲突检查', plc_close_project: '关闭项目',
  plc_compile_block: '编译块', plc_compile_project: '编译项目',
  plc_create_block: '创建块', plc_create_db: '创建DB', plc_create_instance: '创建实例',
  plc_create_project: '创建项目', plc_create_tag_table: '创建标签表',
  plc_create_udt: '创建UDT', plc_create_watch_table: '创建监视表',
  plc_delete_block: '删除块', plc_delete_db: '删除DB', plc_delete_tag: '删除标签',
  plc_delete_tag_table: '删除标签表', plc_delete_udt: '删除UDT',
  plc_delete_watch_table: '删除监视表', plc_download_project: '下载项目',
  plc_export_all_xml: '导出XML', plc_export_block: '导出块',
  plc_export_tags_csv: '导出CSV', plc_find_callers: '查找调用者',
  plc_find_free_address: '空闲地址', plc_find_unused_blocks: '未使用块',
  plc_fio_launch: '启动FIO', plc_fio_write_config: 'FIO配置',
  plc_get_block_details: '块详情', plc_get_block_interface: '块接口',
  plc_get_compiler_errors: '编译错误', plc_get_config: '获取配置',
  plc_get_device_config: '设备配置', plc_get_hardware_info: '硬件信息',
  plc_get_project_info: '项目信息', plc_get_rack_slot: '机架槽位',
  plc_get_state: '获取状态', plc_get_status_info: '状态信息',
  plc_get_tags: '获取标签', plc_go_offline: '下线', plc_go_online: '上线',
  plc_golden_restore: '模板恢复', plc_import_block: '导入块',
  plc_list_backups: '备份列表', plc_list_blocks: '列出块', plc_list_dbs: '列出DB',
  plc_list_devices: '设备列表', plc_list_instances: '实例列表',
  plc_list_tag_tables: '标签表', plc_list_udts: '列出UDT',
  plc_list_watch_tables: '监视表', plc_restore_from_golden: '从模板恢复',
  plc_run_pipeline: '运行流水线', plc_save_project: '保存项目',
  plc_search_tags: '搜索标签', plc_stop_instance: '停止实例',
  plc_switch_to_tcpip: '切换TCP/IP',
  s7_connect: 'S7连接', s7_disconnect: 'S7断开', s7_read: 'S7读取', s7_status: 'S7状态', s7_write: 'S7写入',
  // tia-mcp (15 工具)
  call_fb_in_ob1: '调用FB', compile_project: '编译项目', create_block: '创建块',
  create_ladder_block: '创建梯形图块', create_plc_tags: '创建PLC标签',
  download_to_plcsim: '下载到PLCSIM', export_block: '导出块',
  generate_and_import: '生成并导入', generate_scl_code: '生成SCL',
  go_offline: '下线', go_online: '上线', import_scl_file: '导入SCL',
  list_blocks: '列出块', list_devices: '设备列表', list_udts: '列出UDT',
  // robot-mcp (7 工具)
  control_conveyor: '传送带控制', get_status: '获取状态', go_home: '回原点',
  move_arm_to: '移动手臂', pick_item: '拾取', place_item: '放置', run_pick_cycle: '取放循环',
  // modbus-mcp (6 工具)
  read_coil: '读线圈', read_discrete_input: '读离散输入',
  read_register: '读寄存器', scan_devices: '扫描设备',
  write_coil: '写线圈', write_register: '写寄存器',
  // mitsubishi-mcp (3 工具)
  read_device: '读设备', read_devices: '批量读设备', write_device: '写设备',
}

export function cn(s, map) { return map[s] || s }
