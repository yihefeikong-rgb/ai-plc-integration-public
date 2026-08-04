let meta = #{
    name: "verify-findings-r2",
    description: "对抗性验证复审查2 因 API 限流未完成的 126 条发现，只输出有证据支撑的结论。",
    when_to_use: "复审查验证因限流中断后的补验",
    phases: [
        #{ title: "Verify", detail: "每条发现一个质疑者" },
    ],
};

let verdict_schema = #{
    "type": "object", "required": ["real", "reason", "evidence"],
    "properties": #{
        "real": #{ "type": "boolean" },
        "reason": #{ "type": "string" },
        "evidence": #{ "type": "string" },
    },
};

let findings = [
#{ "file": "orchestrator/workflows/nl_to_plcsim_pipeline.py", "issue": "确认令牌门仅为存在性检查：链路上无任何工具消费/验证该令牌（tia-mcp.create_ladder_block/call_fb_in_ob1 不在 _CONFIRMATION_REQUIRED_OPS 且不接收令牌，bridge 的 plc_compile_project/plc_download_project 也不接收 confirmation_token），传入任意非空占位串即可执行导入LAD→改写OB1→编译→下载→启动Factory I/O 的整条危险链，人工确认机制形同虚设", "severity": "HIGH" },
#{ "file": "orchestrator/workflows/tia_multi_block_pipeline.py", "issue": "确认令牌从未转发给 tia-mcp.import_scl_file（该工具在 tia-mcp 侧属 _CONFIRMATION_REQUIRED_OPS，但 _safety_gate 对空令牌显式放行并委托编排层确认），而编排层仅校验非空占位串，令牌从未被权威消费/验证，工程导入在任意占位串下放行；两侧契约相互矛盾", "severity": "HIGH" },
#{ "file": "orchestrator/workflows/s7_monitor.py", "issue": "以 tag= 参数调用 plc-mcp-bridge.s7_read/s7_write，但 bridge 契约参数为 address（tools_s7.py:146,179），且 core.py WRITE_TOOL_PARAMS 对 s7_write 要求 address；真实 MCP 模式下读取因参数校验失败、写入被 SafetyGate 以缺少目标参数 address 拒绝，已注册运行时工作流完全不可用，测试仅因同签名 mock 而通过", "severity": "MEDIUM" },
#{ "file": "orchestrator/core.py", "issue": "run_adhoc / run() 动态分支 / _run_dynamic 中，步骤在进入 call 前抛异常（step 或 params 非 dict、参数键非字符串）时异常被吞掉后 break，all(s.ok for s in context._steps) 对空列表返回 True，将什么都没执行报告为成功（fail-open），与空步骤列表 fail-closed 的既有约定相矛盾；run_adhoc 是引擎公开接口并经由后端 /workflows/adhoc 暴露", "severity": "MEDIUM" },
#{ "file": "orchestrator/mcp_client.py", "issue": "_from_text 以 '成功'/'已连接'/'已断开'/'📍'/'✅' 子串包含判定成功（fail-open）：语义为否定的文本（如“无法确认写入成功”“未发现已连接设备”）会被归为 text_success；s7_adapter 的 '⚠ 已连接到 {ip}，请先断开' 即被误判为成功", "severity": "LOW" },
#{ "file": "orchestrator/core.py", "issue": "_unwrap_tool_result 字符串分支的 failure_prefixes 含 '错误'/'失败' 且用 startswith 判定，'错误码: 0，无错误' 这类诊断文本会被误判为失败，与同函数注释声称的行为矛盾，也与 mcp_client._from_text（仅 '!','❌','🚫'）的判定不对称", "severity": "LOW" },
#{ "file": "orchestrator/core.py", "issue": "run_adhoc/run()动态分支/_run_dynamic 的 `except Exception: if stop_on_error: break` 吞掉异常：当失败发生在 call_async 的 `**params` 参数展开阶段（params 非 dict 映射）时无步骤被记录，随后 all([])==True 使实际未执行的工作流被误报成功（fail-open），且该路径无任何日志", "severity": "MEDIUM" },
#{ "file": "orchestrator/bootstrap.py", "issue": "连接超时清理残留子进程的分支 `except Exception: pass`（85-86 行）静默吞掉 pool.disconnect_server() 的失败（含 CancelledError），残留 MCP 子进程不可见；shadow 服务器连接失败路径（114-116 行）则完全无清理尝试，与 mcp_client.py 明确声明的“清理不得静默吞掉异常”原则矛盾", "severity": "MEDIUM" },
#{ "file": "mcp_common/audit.py", "issue": "_write_entry 中 _compute_hash/json.dumps(entry) 对不可序列化值（datetime/bytes 等）抛 TypeError，未被 except OSError 覆盖也未映射为 AuditStorageError，从 fail-closed 审计路径裸传播；Windows msvcrt.locking(LK_LOCK) 重试 10 次耗尽的 OSError 也从 _InterProcessLock.__enter__ 裸传播，破坏审计闸门的异常契约。", "severity": "LOW" },
#{ "file": "mcp_common/config.py", "issue": "_looks_like_path 启发式把任何含 /、\\ 或末尾 .[a-z0-9]{2,6} 的字符串静默改写为 base_dir 下绝对路径；排除项仅覆盖 URI/IP/主机名/版本号，形如 abc=def.ghi 的令牌/密码（如 .env 中 INFLUXDB_TOKEN、OPCUA_PASSWORD）会被损坏为 _PROJECT_ROOT\\abc=def.ghi。", "severity": "LOW" },
#{ "file": "mcp_common/config.py", "issue": "load_yaml_config 以配置文件的父目录 p.parent 作为相对路径 base_dir，与 config.yaml 注释声明的\"相对路径从项目根目录解析\"矛盾；经该 API 读取 cartgen.dll_path、logging.audit_log 等相对键会得到双重前缀路径（当前仅 plc-gateway 消费绝对路径的 target.* 键，未实际触发）。", "severity": "LOW" },
#{ "file": "mcp_common/control_target.py", "issue": "require_opcua_endpoint 两个错误分支把含 user:pass 凭据的原始 endpoint 完整拼入 TargetConfigurationError；opcua-mcp/server.py L279 与 robot-mcp/server.py L1055 原样返回给 MCP 工具/CLI，凭据随错误消息泄露。_tmp_verify_endpoint_leak.py 已复现但未修复", "severity": "HIGH" },
#{ "file": "mcp_common/tiaworker_client.py", "issue": "run() 中 L195/L205/L309 三处 except Exception 将任意 str(exc) 内联进返回给 MCP 客户端的错误 dict：泄露内部路径/配置细节，且 L309 兜底把编程错误伪装为 EXEC_ERROR，掩盖真实失败", "severity": "MEDIUM" },
#{ "file": "mcp_common/audit.py", "issue": "_load_last_hash L254-258 对全空白日志文件静默返回零锚 0*64 并重起链，违反模块 fail-closed 契约；日志被截断为空白后 verify() 仍返回 True，截断+重锚追加的篡改无法被检测", "severity": "MEDIUM" },
#{ "file": "safety/validator.py", "issue": "_check_interlock_rules 在全部规则通过后即写入 _last_write_time，但全局范围检查与跳变检测在其后运行；被第4/5步拒绝的写入仍推进冷却时间戳，导致后续合法写入被'冷却时间未到'误拒，被拒写入反而延长冷却锁定期。", "severity": "MEDIUM" },
#{ "file": "safety/shadow_simulator.py", "issue": "_check_value_bounds/_check_change_rate 以 isinstance(value,(int,float)) 判定数值，bool 作为 int 子类被当作数值写入 _history（0/1），与 validator 显式排除 bool 的 is_numeric_scalar 不一致；同一标签后续数值写入与 1 比较触发虚假 10 倍跳变拒绝，两层安全逻辑对 bool 语义矛盾。", "severity": "MEDIUM" },
#{ "file": "safety/audit.py", "issue": "_read_tail_hash 注释声称与 mcp_common/audit.py _load_last_hash 语义完全一致，但非空日志尾部仅剩空行时 _load_last_hash 静默返回 \"0\"*64 重新锚定，而 _read_tail_hash fail-closed 抛 AuditStorageError；静默重锚正是该模块声称防御的截断篡改路径，AuditLogger.__init__ 仍走弱化实现。", "severity": "MEDIUM" },
#{ "file": "safety/validator.py", "issue": "熔断计数与冷却时间戳为各进程独立 WriteValidator 实例的内存状态；审计链用文件锁解决跨进程并发，validator 无对应机制，多进程轮流写入可绕过冷却限制，单进程熔断不阻止其他进程继续写入。", "severity": "MEDIUM" },
#{ "file": "safety/validator.py", "issue": "if cooldown: 使 cooldown_seconds=0（falsy）或负值（恒不满足 elapsed<负数）的冷却保护静默失效，配置边界语义不明时冷却规则不生效。", "severity": "LOW" },
#{ "file": "safety/confirmation.py", "issue": "_connection() 的 try/except 仅捕获 sqlite3.Error；store_path.parent.mkdir()/sqlite3.connect 的 OSError（PermissionError/FileExistsError）未包装为 ConfirmationError，从 consume() 穿透。modbus/mitsubishi/robot 调用方只捕获 ConfirmationError，未处理 OSError 经 FastMCP 把含 sqlite 存储完整路径的异常消息暴露给客户端", "severity": "MEDIUM" },
#{ "file": "safety/confirmation.py", "issue": "consume() 内 ROLLBACK 失败被 except sqlite3.Error: pass 静默吞掉（无日志）。失败后缓存的连接句柄可能残留未完成事务，后续 BEGIN IMMEDIATE 全部报 cannot start a transaction within a transaction，防重放路径连续失败且日志无痕", "severity": "MEDIUM" },
#{ "file": "safety/validator.py", "issue": "_load_interlock_rules 只校验规则结构不校验字段类型；若 interlock-rules.yml 的 max_value/min_value/cooldown_seconds 为字符串等非数值，_check_interlock_rules 中比较运算抛 TypeError 穿透 validate()。modbus/mitsubishi/edge-gateway 调用 validate() 处均无 try/except，本应 fail-closed 的写拒绝变成未处理异常", "severity": "LOW" },
#{ "file": "mcp-servers/tia-mcp/server.py", "issue": "_safety_gate() 中确认校验条件为 `if confirmation_token and (...)`：调用方省略 confirmation_token 时直接短路放行，download_to_plcsim / import_scl_file / compile_project / full_pipeline 等危险工程操作可绕过一次性人工确认执行（docstring 亦自述'未提供令牌时保持既有契约放行'）", "severity": "HIGH" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "write_coil/write_register 消费确认令牌后仅记录 write 事件，approver 身份与 audit_id 不落入 HMAC 审计链（仅 mitsubishi-mcp 有 _audit_confirmed 闭环），审计链无法证明'谁人工批准了本次写入'，确认事件与审计链脱钩", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/backend/routes/orchestrator.py", "issue": "/confirmations 签发端与写入端条件错位：签发侧 check_write 用原始地址（如 register.100）且后端全局 SafetyGate 未注册 bit_reader，需确认的目标恒返回 422/409/503，人工确认写入流程在 modbus/opcua/s7 路径整体不可达，确认机制事实性失效", "severity": "LOW" },
#{ "file": "edge-gateway/src/ai_client.py", "issue": "decide_control 的兜底 alert JSON 含 \"value\": null，违反自身 _DECISION_SCHEMA 的 value 类型(number|boolean)，parse_decision 对兜底输出必返 None，app.py 的'已转为 alert'签名识别成为死代码；同时模型合法输出 wait/alert 且 value 为 null 时也被计入硬校验失败，连续 3 次即永久置位 _ai_fused（无复位机制），AI 控制链路在重启前被误熔断禁用", "severity": "HIGH" },
#{ "file": "edge-gateway/src/ai_client.py", "issue": "_DECISION_SCHEMA 允许 write 的 value 为 boolean，而 _exceeds_max_delta 对 value 或 current_value 任一侧为 bool 时直接返回 False，使代码强制的 50% 跳变保护对数值目标（如 MW14）可被 true/false 完全绕过，仅剩 s7_adapter 的 parse_write_value 类型检查兜底", "severity": "LOW" },
#{ "file": "edge-gateway/src/app.py", "issue": "run() 的指数退避逻辑失效：scan_once 将逐标签读取异常吞入 status:'error'，ai_control_loop/_write_influx 的异常也在内部捕获，断连期间 consecutive_failures 恒为 0，'持续失败指数退避避免 30s 空转'的注释意图不成立", "severity": "LOW" },
#{ "file": "edge-gateway/src/app.py", "issue": "传给 AI 的 available 可写白名单包含只读/急停标签（如 M1.2 E-Stop Status），而 FORBIDDEN_TARGET_PATTERNS 是对地址字符串（如 'M1.2'）做正则匹配、不可能命中（仅匹配 ESTOP/SAFETY 等名字），急停/只读标签的防写完全依赖 resolve_s7_write_address 地址映射单层保护", "severity": "LOW" },
#{ "file": "mcp-servers/plc-mcp-bridge/tools_s7.py", "issue": "s7_write 全部拒绝路径（约 10 处）调用 _audit.log(\"write_rejected\",...,success=False) 时未传 operator，默认 \"ai-agent\"；生产环境下 _ensure_production_actor 对 ai-agent 抛 AuditConfigurationError 且未被捕获，每次被拒写入以未处理异常崩溃、拒绝审计不落盘", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-mcp-bridge/tools_s7.py", "issue": "require_bits 使用语义名（DB1.SafetyOK/DB1.EmergencyStopOff），_read_safety_bit 用 S7Adapter.read_address 解析必然 ValueError（_parse_addr 返回 UNKNOWN）恒返回 None，validator fail-closed 使 M0.1/MW14 的 s7_write 永远被互锁拒绝，写入路径实际死路", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-mcp-bridge/tools_pipeline.py", "issue": "async 工具处理器（tools_pipeline/tools_plcsim/tools_project/tools_types/tools_export/tools_diagnostics/tools_hardware 及 _helpers.plc_apply 第274行）在事件循环内同步阻塞调用 _run_tiaworker/_run_python（超时最长 300-600s），未用 asyncio.to_thread（tools_blocks/tools_tags 已用），长任务期间冻结所有并发 MCP 请求", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-mcp-bridge/tools_plcsim.py", "issue": "stop_instance/restore_from_golden/archive_to_golden/switch_to_tcpip（及 tools_pipeline 的 download_project/run_pipeline/golden_restore）仅依赖客户端自报 confirm/dry_run 布尔，无 _audit_gate 且子进程脚本 p3_flow/download_to_plcsim/plcsim_api 经 grep 确认均无审计写入，高影响 PLC 控制操作零 HMAC 审计记录", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-mcp-bridge/tools_s7.py", "issue": "一次性人工确认令牌在步骤5先被消费，步骤6才执行审计闸门 begin_control_operation 与真实写入；若写入阶段失败（连接断开/审计存储故障），令牌已被烧掉且无写入发生，下次尝试必须重新签发", "severity": "LOW" },
#{ "file": "mcp-servers/plc-mcp-bridge/s7_adapter.py", "issue": "read_merker/write_merker 不校验 bit 0-7 范围（util.get_bool 越界位抛异常），read_byte 忽略 size 仅返回 data[0]（size=0 时 IndexError）；模块文档声明可被 EdgeGateway 独立 import，直连调用存在越界风险", "severity": "LOW" },
#{ "file": "mcp-servers/plc-gateway/contracts/safety_chain.py", "issue": "check_all() 中确认令牌在 line 155 先被 check_confirmation→consume_token 一次性消费，而预览令牌/目标/风险检查在 line 161-163 的循环中才求值；预览令牌无效或目标不匹配时确认令牌已被不可逆烧毁（审计含 TOKEN_CONSUMED 而无 APPLY_STARTED），与 network_patch.py 声明的'漂移时令牌保持未消费'语义矛盾。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-gateway/providers/tiacommander.py", "issue": "apply_patch()（line 484-534）任一操作失败 break 后返回的顶层 ProviderResult 未设置 error 与 reconcile_required：error 变成'未知错误'（__post_init__），部分写入真实 TIA 工程后 tia_apply_block_patch 路径按普通 error 上报而非 reconcile_required，存在重试二次写入风险；真实错误详情被埋在 result.operations 中。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/plc-gateway/workflows/network_patch.py", "issue": "_validate_operation()（line 154-156）与 tiacommander.apply_patch（line 511-516）未排除 bool：isinstance(True,int) 为 True，network_index:true 通过校验并以 networkIndex=true 下发；而 guarded_apply.validate_guarded_apply 显式拒绝 bool，三层校验不一致。", "severity": "LOW" },
#{ "file": "mcp-servers/plc-gateway/contracts/preview_apply.py", "issue": "AuditLog.record()（line 250-257）先更新内存 _last_hash/_entries 再 _persist 落盘；落盘抛错时内存链已前移到未落盘条目，后续条目基于该 hash 续链，verify_chain 将对该进程后续记录永久报链损坏。", "severity": "LOW" },
#{ "file": "mcp-servers/opcua-mcp/server.py", "issue": "双熔断策略不一致且状态展示缺失：safety/validator.py 将互锁保护性拒绝（require_bits 位读取失败、规则范围越界、禁写标签、非数值输入）计入 consecutive_errors，连续 3 次即熔断并阻塞全部标签的写入；而 opcua_safety 本地熔断明确对保护性拒绝不计入（count_fuse=False）。opcua_get_status 只展示本地熔断，root 熔断已触发时仍显示『🟢 正常』，操作员无法感知所有写入已被静默阻塞", "severity": "MEDIUM" },
#{ "file": "mcp-servers/opcua-mcp/opcua_safety.py", "issue": "熔断状态持久化非原子：FUSE_STATE_FILE 用 write_text 直接覆写（无临时文件+rename），trip_fuse/_save_fuse_state 写入中途崩溃会留下空或半写 JSON，_load_fuse_state 捕获异常后静默以 tripped=False 默认值启动，『防止重启绕过熔断』的保证在崩溃窗口失效（熔断被旁路）。此外 max_errors 从文件读取无范围校验（0/负数导致首次失败即熔断，超大值导致熔断永久失效）", "severity": "MEDIUM" },
#{ "file": "mcp-servers/opcua-mcp/server.py", "issue": "所谓『读回验证』未真正验证：readback 仅拼进返回消息，未与写入值比较；PLC 限幅或并发覆盖导致写入未生效时仍以 success=True 记录审计并重置熔断计数，给出虚假的成功确认", "severity": "LOW" },
#{ "file": "mcp-servers/opcua-mcp/server.py", "issue": "一次性人工确认令牌在所有检查通过后、执行写入前消费，任何写入异常（连接丢失、UA 错误、类型转换失败）都会导致令牌已被作废、重试需重新签发；步骤 5 注释声称『避免写入失败时令牌已被作废』与实际行为矛盾", "severity": "LOW" },
#{ "file": "mcp-servers/mitsubishi-mcp/test_mc_protocol.py", "issue": "test_x_input/test_y_output 断言十进制偏移(10/20)，而默认 FX 系列下 _parse_offset 按八进制解析(int('10',8)=8、int('20',8)=16)，与 mc_protocol.py 注释声明的 X10->0x000008 一致但与测试矛盾，模块自带测试必然失败；X/Y 进制语义变更未同步更新测试", "severity": "MEDIUM" },
#{ "file": "mcp-servers/mitsubishi-mcp/server.py", "issue": "人工确认清单(_MELSEC_CONFIRM_PREFIXES+Y/L/S/B/F 及 M/D>=8000)未覆盖 T/TN/C/CN 定时器/计数器与 V/Z/ZR 变址寄存器等可影响控制逻辑的设备；safety.validator 的 S7 模式对这些地址永不匹配，故 write_device(TN5/V0 等)可绕过确认门静默直写，与模块声明的 fail-closed 控制型地址策略相悖", "severity": "MEDIUM" },
#{ "file": "mcp-servers/mitsubishi-mcp/server.py", "issue": "_read_points 在 _io_lock 之外调用 _close_connection()(parse_read_response 抛 MCFrameError 时)，可能切断并发任务在同一共享连接上的进行中帧交换(对方依赖重试恢复，不会帧错配)，与 _send_frame 内部关闭一律持锁的纪律不一致，属竞态隐患", "severity": "LOW" },
#{ "file": "mcp-servers/mitsubishi-mcp/mc_protocol.py", "issue": "build_write_request 位写入对非 0/1 值静默强转(0x10 if value else 0x00，value=5 也会写 ON)，协议层自身不 fail-closed；仅靠服务端 _melsec_write_guard 前置拦截，直接使用该协议函数的调用方不受保护", "severity": "LOW" },
#{ "file": "mcp-servers/mitsubishi-mcp/server.py", "issue": "write_device 第3步 _audit_confirmed 的 except 仅捕获 AuditStorageError/AuditConfigurationError，但审计层 _InterProcessLock.__enter__（open 锁文件、msvcrt.locking）与 _load_last_hash 的 open 均未包裹，可抛裸 OSError/PermissionError（mcp_common/audit.py:61-63,246）。该异常未捕获地逃逸到 MCP 层：确认令牌已被消费却无结构化错误返回、熔断计数不增加，原始异常（可能含审计/锁文件内部绝对路径）暴露给客户端。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/mitsubishi-mcp/server.py", "issue": "write_device 第5步 _audit_control_intent 触发的裸 OSError/PermissionError 落入通用 except (…, OSError, …) 分支，被误报为『写入失败，请稍后重试』；审计链/审计存储故障被伪装成 PLC 通信故障，fail-closed 审计门失效原因对运营方不可见。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "模块级 int(settings.get(\"safety_max_consecutive_errors\",\"3\")) 无保护：非数字环境变量导致导入崩溃，0/负数导致 _write_fuse_tripped 的 >= 比较恒真、首次写入即被熔断；与 safety/validator.py 对同一键的 _parse_max_errors fail-closed 解析（回退 1）不一致。", "severity": "HIGH" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "读路径（read_coil/read_register/read_discrete_input 的异常处理）在 audit.log 失败时调用 _record_write_error()，读侧审计故障会累计递增写入熔断计数，可无任何写失败地阻塞全部写入直至人工 modbus_reset_fuse。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "写路径先消费一次性确认令牌再执行 audit.begin_control_operation；后者抛异常（如生产环境缺 AUDIT_HMAC_KEY、审计存储损坏）时令牌已被烧掉、熔断计数被 catch-all 累加，且返回 _WRITE_ERROR（'Modbus 写入失败（已记录审计日志）'）——实际未发起写且审计未落盘，错误信息双重误导。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "scan_devices 对 10 个从站串行读共享客户端，每个离线从站占用事务 RLock 至多 3s，全离线扫描约 30s+ 阻塞线程池与同客户端并发调用；且 pymodbus count_until_disconnect=3 在连续超时后关闭连接，扫描中途强制重连。", "severity": "LOW" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "read_register 在 count=1 时返回 values 列表，而 read_coil/read_discrete_input 在 count=1 时返回标量 value，单点读取的输出结构不一致，下游按 value 解析寄存器读取会 KeyError。", "severity": "LOW" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "_write_fuse_tripped 检查与设备写执行间存在 TOCTOU：并发写调用可在计数达阈值前同时通过熔断检查并执行，'连续写失败熔断'可被并发写绕过。", "severity": "LOW" },
#{ "file": "mcp-servers/modbus-mcp/server.py", "issue": "读路径 audit.log（第227/229/236/259/266/286/297行）未传 operator，默认 \"ai-agent\"。生产模式下 mcp_common/audit.py 的 _ensure_production_actor 会抛 AuditConfigurationError，使每次读（含成功）都落入外层 except：返回 _READ_ERROR、_reset_client() 丢弃共享连接、且 _record_write_error() 把读侧审计失败计入写熔断——连续 3 次读后全部写被熔断，需人工重置。读侧失败被误当作设备写失败并级联阻塞写路径。", "severity": "HIGH" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "_is_blacklisted_hotkey 只拦截恰好单个危险键（len(pressed)==1）和黑名单组合的子集；\"危险单键+修饰键\"组合可绕过，如 hotkey(['shift','delete'])（Windows 资源管理器永久删除）、hotkey(['ctrl','f2'])，违背 88-92 行注释声明的\"防止 hotkey 绕过单键危险键黑名单\"意图", "severity": "HIGH" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "tool_move_mouse/tool_drag 的 duration 参数缺少 duration>=0 校验（与 tool_click/tool_type_text 对 interval<0 的拒绝不一致）；负 duration 传入 pyautogui 内部 time.sleep 可能抛 ValueError 或静默瞬时移动，只回显模糊的\"工具执行失败\"", "severity": "LOW" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "未知工具名分支（306 行）把 {\"error\":...} 塞进成功 result 返回，违背模块自身 ToolRejectedError 注释（120-125 行）\"拒绝必须回送 JSON-RPC error，避免客户端误判为已执行\"的错误语义", "severity": "LOW" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "_to_int 对浮点输入静默 int() 截断（如 x=10.9→10）并接受数字字符串，坐标/次数精度丢失无告警；对 bool 反而显式拒绝，与模块 fail-closed 的严格校验取向不一致", "severity": "LOW" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "tool_screenshot 与 tool_locate_on_screen 的 region 仅校验四元素数组，未校验 x/y>=0、w/h>0 及屏幕边界；越界/负坐标/零宽高区域由平台 ImageGrab 静默裁剪，返回尺寸与请求不一致且无明确\"区域无效\"错误", "severity": "LOW" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "mcp_recv() 中 readline() 的 UnicodeDecodeError（非法 UTF-8 字节）与 json.loads 的 RecursionError（深度嵌套 JSON）均未捕获，单条坏数据即可使整个服务器进程崩溃，与 docstring 声称的\"避免单行坏数据杀死服务器\"设计目标矛盾", "severity": "HIGH" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "未知工具名走 else 分支把 {\"error\": ...} 塞进 JSON-RPC success result（L305-312），与认证(-2)/确认门(-3)/黑名单(-4) 统一使用 error 的语义不一致，客户端会把\"工具不存在\"误判为执行成功", "severity": "MEDIUM" },
#{ "file": "mcp-servers/desktop-mcp/server.py", "issue": "mcp_recv() 的 except OSError 将任意读错误吞掉并当作 EOF 返回 None，主循环静默 break 退出，瞬时性读取失败被误判为正常断开且无任何日志", "severity": "MEDIUM" },
#{ "file": "mcp-servers/robot-mcp/server.py", "issue": "_load_estop_latch (L256-265) 用 except Exception: pass 静默吞掉读取/JSON 解析错误并返回 False（fail-open）；配合 _save_estop_latch (L273-277) 非原子的直接 write_text，崩溃产生的半截闩锁文件会让『急停恢复后必须重新确认』在重启后被静默清除，且 _latch_loaded 置位后进程内不再重试。应改为解析/读取失败时 fail-closed（视为需要重确认）。", "severity": "HIGH" },
#{ "file": "mcp-servers/robot-mcp/server.py", "issue": "_pick_item/_place_item/move_arm_to 中大量 write_io 返回值被忽略（如 L731 grab、L829-831 conveyor_exit、L704/715/723/742/750/793/801/809/813/821/885/891/897/900/907/914/921）：执行器写失败（急停中途触发/连接断开）仍按成功继续，_place_item 在 conveyor_exit 写失败时仍返回 ok 并审计为『物料已放置到出口，已运走』，_pick_item 在 grab 写失败时陈旧 sensor_item_detected 仍可导致误报抓取成功。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/robot-mcp/deploy_pnp.py", "issue": "step4_download (L165-170) 的 p3_flow.py --download-only 兜底路径仅以 returncode==0 判定下载成功，未要求主路径所需的设备级成功回执（『TiaWorker 下载成功』标记）；这与 L154-158 注释自己声明的『returncode==0 单独不能证明下载成功』矛盾，失败路径反而使用更弱的校验，可能把未确认的下载当作成功。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/robot-mcp/server.py", "issue": "OPC UA 失败处理无超时与退避：connect_opcua (L162-175) 无 timeout 参数，read_io 中读失败即 _drop_opcua (L294-298) 置空客户端，之后每次 I/O 的 ensure_connected 都新建连接全量重连；目标 IP 不可达时 connect() 可能长期阻塞事件循环，所有工具调用被反复拖住。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/robot-mcp/server.py", "issue": "connect_snap7 (L179-188) 失败路径未释放资源：connect() 抛异常或 get_connected() 返回 False 时仅把 _snap_client 置 None 返回 False，未调用 disconnect()/close()，连接失败时 socket 句柄泄漏。", "severity": "LOW" },
#{ "file": "mcp-servers/robot-mcp/server.py", "issue": "ensure_disconnected (L468-473) 用裸 except Exception: pass 静默吞掉全部清理写失败且无任何日志，失败不可见；且全模块无调用点（grep 确认），该安全清理路径实际是死代码，未能承担停机时去使能输出的兜底职责。", "severity": "LOW" },
#{ "file": "mcp-servers/robot-mcp/verify_pick_and_place.py", "issue": "L111 与 L122 使用裸 except: 吞掉所有异常（包括 KeyboardInterrupt/SystemExit），节点读取失败时既无日志也无细节输出，诊断脚本的关键失败被静默隐藏，误导排障。", "severity": "LOW" },
#{ "file": "mcp-servers/robot-mcp/deploy_pnp.py", "issue": "_import_one_scl (L109-119) 中 scl_path.read_text/write_text 等文件 I/O 不在 try 内，step2_import_scl 只检查 TIA_WORKER 存在未检查 SCL_FC 存在；pnp_fc.scl 缺失或不可读时异常直接穿透 main()，以裸 traceback 崩溃而非返回『SCL 导入失败』的受控失败路径。", "severity": "LOW" },
#{ "file": "mcp-servers/tia-mcp/server.py", "issue": "_safety_gate 人工确认闸门 fail-open：download_to_plcsim/import_scl_file/compile_project/full_pipeline 的 docstring 声称 confirmation_token 必填且 fail-closed，但实现仅当令牌非空才消费（if confirmation_token and (...)），令牌缺失（含 validator 返回 needs_confirmation=True 时）直接放行，MCP 客户端可不携带人工确认令牌直接执行 PLC 下载等危险工程操作", "severity": "CRITICAL" },
#{ "file": "mcp-servers/tia-mcp/create_plc_tags.py", "issue": "create_tags 在 API 创建全部失败（created==0 且 errors>0）时自动降级到 create_tags_via_xml，该路径先 TagTables.Delete 删除整个标签表再仅导入本次传入的标签；已存在的同表标签被静默清空，破坏工具'幂等，已存在则跳过'的契约，属无确认的破坏性工程数据删除", "severity": "HIGH" },
#{ "file": "mcp-servers/tia-mcp/call_fb_in_ob1.py", "issue": "insert_fb_calls 在导入/编译前无条件删除 Main(MOB1)/MasterIO/MasterIO_DB 块，失败时异常逃逸但 tia_session 的 finally 仍无条件 project.Save()，把删除持久化；任何瞬态导入或编译错误都会永久丢失用户原有 OB1 且无备份（代码注释也承认旧块无备份）", "severity": "HIGH" },
#{ "file": "mcp-servers/tia-mcp/server.py", "issue": "_require_scl_semantic_safety 只提取第一个 VAR_OUTPUT..END_VAR 段的输出名，输出声明在 VAR_IN_OUT/VAR/静态区或无 VAR_OUTPUT 段时 motor_outputs 为空，急停/过载/正反转互锁语义闸门整体静默返回空列表，缺少急停与过载引用的电机类 SCL 块可绕过硬阻断直接导入", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tia-mcp/plcsim_network.py", "issue": "switch_to_tcpip 中 SetIPSuite 失败仅打印警告后继续 instance.Run() 并输出 OK TCP/IP RUN，不校验实例实际绑定的 IP 是否为批准目标地址；配合下载闸门只校验实例名不校验 IP，IP 漂移/绑定失败会被上报为成功", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tia-mcp/tia_session.py", "issue": "headless 会话的 session_pids = 连接后快照 − 基线快照，存在 TOCTOU：并发 headless 会话在本会话连接窗口内启动的 TIA Portal 进程会被记入 session_pids，finally 中 _kill_tia_processes 会 taskkill 掉其他会话的进程，注释声称要避免的并发误杀竞态未真正消除", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tia-mcp/server.py", "issue": "_run_worker 对 TiaWorker 返回合法 JSON ok:true 但进程退出码非零（或 ok:false 但变更可能已部分生效）的变更命令直接返回普通错误、不设置 OUTCOME_UNKNOWN/reconcile_required，与超时/无输出路径的 outcome_unknown=is_mutating 处理不一致，调用方可能重试结果实际未知的变更操作", "severity": "LOW" },
#{ "file": "mcp-servers/tiacommander-mcp/logs/tiacommander-2026-07-24.log", "issue": "telemetry 失败路径未处理：422 校验错误(machine_id/license_key 长度不符)被无限重试，原始服务端错误响应(含 license_key/machine_id 字段名)逐条写入日志；StartHeadlessTelemetry 溢出异常仅以 WARNING 吞掉", "severity": "LOW" },
#{ "file": "mcp-servers/tiacommander-mcp/logs/tiacommander-2026-08-04.log", "issue": "模块在 DEBUG 级记录完整 JSON-RPC 请求(含工具参数与 _meta 元数据)，参数中的块 XML/路径会落盘；且 README 声明失败调用的 error message 与设备上下文会发送给厂商 telemetry，错误信息存在本地日志与远程双重泄露路径", "severity": "LOW" },
#{ "file": "mcp-servers/tiacommander-mcp/docs/README.md", "issue": "危险操作确认是软门槛：确认字符串内嵌在工具面（工具描述）中，AI 客户端自身即可满足，无法区分人类批准与代理自授权。download_to_device（含 mode=hardware/hardware_software、stopModules=true 停止运行中 PLC）、upload_station、delete_block(force)、delete_network、set_network_config、update_project、delete_unused_types、delete_library_folder 等真实控制/破坏性操作仅由该字符串把关，绕过确认无额外防护。", "severity": "HIGH" },
#{ "file": "mcp-servers/tiacommander-mcp/docs/README.md", "issue": "stdio JSON-RPC 通道无任何认证/授权边界（README 自行声明）：任何本地进程或同账号下恶意软件即可启动 TiaCommander.exe 并驱动全部 16 个工具，包括启动 TIA Portal、打开工程、下载到真实 PLC 与停止模块；且无任何可归属到操作者身份的审计链（本地仅调用统计与遥测），无法事后追溯谁执行了控制操作。", "severity": "HIGH" },
#{ "file": "mcp-servers/tiacommander-mcp/CHANGELOG.md", "issue": "安全关键控制动作护栏不足：v2.20.0 记载硬件下载（mode=hardware/hardware_software）会自动停止 PLC 模块，v1.12 起该类危险操作仅依赖软确认字符串；而 diagnostics→configure_connection（程序化设置下载连接）与 go_online 未列入 README 确认表即可触发，触及运行中 PLC 的停止/在线态切换等安全相关行为，缺少超出软门槛的硬性人因确认。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tiacommander-mcp/docs/README.md", "issue": "遥测默认开启且无退出开关（README 明示只能靠防火墙人工拦截或离线使用），负载含 license_key、machine_id、PLC 设备订单号/固件、硬件目录条目、会话 UUID、AI 客户端与错误上下文（日志中遥测服务 422 响应泄露 machine_id/license_key 字段）；在工业控制环境中属敏感资产信息默认外发，且 LICENSE.txt 仅描述为'使用统计与错误报告'，与实际外发内容不符。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tiacommander-mcp/logs/tiacommander-2026-08-04.log", "issue": "服务器以 DEBUG 级将完整 JSON-RPC 请求/响应明文写入 logs/*.log（日志可见 initialize 客户端信息、tools/list 请求与响应全文逐条落盘）；一旦发生携带敏感参数的工具调用（import_xml_inline 的块 XML、工程路径、标签/DB 内容等），负载会明文留存，且日志文件与模块一同分发、无轮换与加密说明，v2.9.1 声称的'输出清洗'未覆盖文件日志。", "severity": "MEDIUM" },
#{ "file": "mcp-servers/tiacommander-mcp/docs/README.md", "issue": "admin→open_file（用默认 Windows 应用程序打开文件）与 save_export（base64 解码写入文件）的工具描述未声明任何路径校验/白名单限制（如限制在导出存储目录内）；若实现不校验，AI 客户端可通过路径参数打开/启动任意本地文件或写入任意路径，属未校验输入的潜在面（二进制实现无法静态验证，文档层面无任何限制说明）。", "severity": "LOW" },
#{ "file": "ai-plc-assistant/backend/routes/generate.py", "issue": "generate_ladder_code/generate_scl_code/generate_xml_code 为 async 端点却同步调用阻塞式 LLM chat()（30s 超时），未用 asyncio.to_thread；一次生成请求会长时间阻塞整个事件循环，期间所有 API（含 health/chat）全部停滞", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/backend/routes/generate.py", "issue": "/export 与 /export/download 的 variables/networks 为无 schema 校验的 dict 列表，null 字段（如 address/name/elements）经 _dict_to_program 传入后触发 None.strip()/startswith()/len() 抛 AttributeError/TypeError，未处理直接 500", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/backend/routes/conversations.py", "issue": "AddMessage 的 role/content/msg_type 无长度与取值校验（对比 chat 端点的 8KB/32KB 上限），超大内容与任意角色（含 system）可绕过限额永久入库，get_conversation 无分页全量返回", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/backend/routes/prompts.py", "issue": "list_templates/list_categories/get_template 三个 GET 端点未挂 require_local_session，与后端其余模块（含本模块 create/update/delete）的认证策略不一致，模板内容可未认证读取", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/backend/main.py", "issue": "ProjectStore 路径由 conversations_db.replace('conversations','projects') 推导，配置的路径不含该字面量时静默返回原路径，对话与项目两个 store 将共用同一 DB 文件", "severity": "LOW" },
#{ "file": "ai-plc-assistant/backend/routes/conversations.py", "issue": "list_conversations/list_projects 的 limit 参数无 ge/le 约束，limit=-1 时 SQLite LIMIT -1 视为无上限，返回全部记录", "severity": "LOW" },
#{ "file": "ai-plc-assistant/backend/routes/search.py", "issue": "search() 对中文查询分流到 LIKE(search_simple)，而 search_by_type() 始终走 FTS5 MATCH 整词短语匹配，中文子串查询带 type_filter 时结果为空且与 search 行为不一致", "severity": "LOW" },
#{ "file": "ai-plc-assistant/frontend/src/components/orchestrator/api.js", "issue": "apiGet 未携带 localControlHeaders()（X-Local-Api-Token），而后端 /api/orchestrator/* 全部 GET 端点（workflows/tools/servers/monitor/dynamic）都依赖 require_local_session；配置了 LOCAL_API_TOKEN 时 OrchestratorPanel 所有加载请求返回 401/503，面板整体不可用，与同文件 apiPost/apiDelete 行为不一致", "severity": "HIGH" },
#{ "file": "ai-plc-assistant/frontend/src/hooks/useConversation.js", "issue": "token 节流缺陷：flushToken 回调不重置 tokenFlushRef.current，onToken 中 if(tokenFlushRef.current) return 使第一次 40ms flush 后不再调度任何新 flush，流式生成期间 UI 在首段内容后冻结，直到 onDone 才一次性更新全文", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/frontend/src/hooks/useConversation.js", "issue": "构造 LLM 上下文时当前用户消息重复：messagesRef.current（setMessages 已加入本条消息并重渲染）slice(-6) 后又追加 {role:'user',content:text}，新建对话首次发送（ensureConversation 必经网络 await）时必然把同一条用户指令连续发送两次给模型", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/frontend/src/components/Dashboard.jsx", "issue": "loadSafetyLevel 对持久化的 device-control(L3) 直接恢复显示，缺少 GlobalStatusBar 中实现的 L3 fail-closed 清除逻辑（其测试还断言恢复 L3）；两处对同一 localStorage 键安全语义相反，当前仅靠组件挂载顺序掩盖，属安全相关逻辑分叉", "severity": "MEDIUM" },
#{ "file": "ai-plc-assistant/frontend/src/components/RobotPanel.jsx", "issue": "pickItem/placeItem/runAutoCycle 用闭包中的 executing 做重入保护，快速连击（重渲染前）可重复通过守卫，调度两套重叠的定时动作序列，状态机交错且 setExecuting(false) 提前释放", "severity": "LOW" },
#{ "file": "ai-plc-assistant/frontend/src/components/chat/messages/CodeMessage.jsx", "issue": "CODE 类型消息无代码时回退占位错误地传入 MSG_TYPES.TOOL_CALL，渲染为「工具调用/无调用详情」，应为 CODE 占位", "severity": "LOW" },
#{ "file": "ai-plc-assistant/frontend/src/api.js", "issue": "streamChat 收尾用 buffer.includes('[DONE]') 宽松判断：流提前终止且末尾残缺行 token 内容恰含字面量 [DONE] 时被误判为正常完成，绕过 fail-closed 错误上报", "severity": "LOW" },
#{ "file": "ai-plc-assistant/frontend/src/components/orchestrator/OrchestratorPanel.jsx", "issue": "deleteWorkflow 由 Trash 图标一键触发，删除自定义工作流无确认弹窗（同库其他破坏性操作均有二次确认），误点即丢失编辑的工作流定义", "severity": "LOW" },
#{ "file": "scripts/start_plcsim_gui.py", "issue": "_resolve_lnk_target() 解析 .lnk 的 LinkInfo 偏移全部错位：把 [4:8]（实为 LinkInfoFlags）当 header_size、把 [16:20]（实为 CommonNetworkRelativeLinkOffset）当 LocalBasePathOffset（正确位置 [12:16]），并用 ShellLinkHeader 的 IsUnicode 位而非 LinkInfoFlags bit0 判断路径编码；对常规本地快捷方式恒返回空串，Start Menu 搜索路径静默失效且异常被吞。", "severity": "MEDIUM" },
#{ "file": "scripts/p3_flow.py", "issue": "编译失败不中止控制链：step2_compile() 返回 False 后 main() 仍无条件执行 step2_download()，且下载子进程未传 --compile-first，会把编译失败前的过期程序下载到已 RUN 的 PLCSIM，与步骤 1 失败即 sys.exit(1) 的处理不一致，违背动态控制链 fail-closed 原则。", "severity": "MEDIUM" },
#{ "file": "scripts/gen_bat.py", "issue": "生成的 run_p3_complete.bat 在 restore/stop 命令中硬编码实例名 'factoryio'（第72、133行）而非 target.plcsim_instance，违反本脚本自己声明的'只从 config 读取、拒绝硬编码漂移'契约；一旦实例名配置变化，生成的 bat 会静默操作错误实例。", "severity": "MEDIUM" },
#{ "file": "scripts/gen_bat.py", "issue": "第141行 line.encode('ascii') 未捕获 UnicodeEncodeError：golden_zip/storage_path/工程路径含非 ASCII（中文）字符时生成器直接崩溃退出，不产出 .bat 且无友好报错。", "severity": "LOW" },
#{ "file": "scripts/launch_factory_io.py", "issue": "SCENE_FILE（config factory_io.scene_path）被校验和打印但从未使用：不写入 auto.cfg，也不作为参数传给启动的进程，配置场景静默不加载，属死配置逻辑缺口。", "severity": "LOW" },
#{ "file": "scripts/p3_flow.py", "issue": "_query_instance_state() 用 instance_name in line 子串匹配 + 依赖 '—' 分隔符解析 list 输出：存在名称互为子串的实例时会取错状态；子进程以 locale 编码写管道时父进程 utf-8 解码得替换字符致 '—' 永不匹配，函数静默返回 None。", "severity": "LOW" },
#{ "file": "scripts/verify_phase2.py", "issue": "第78行 check('审计日志写入', True) 硬编码通过，未断言 logger.log 返回值或审计文件内容，审计写入失败时验证脚本仍报告 PASS，验证失真。", "severity": "LOW" },
#{ "file": "scripts/p3_flow.py", "issue": "编译步骤失败后流程不中止：step2_compile() 返回 False 仍继续执行 step2_download()，下载成功还会调用 step2_archive() 覆盖 golden backup 恢复基线；而 plcsim 步骤失败是 sys.exit(1)。失败路径未处理，可能把编译已确认失败后的状态写入基线。", "severity": "HIGH" },
#{ "file": "tests/test_tools_pipeline.py", "issue": "test_launch_success 的 shell 断言逻辑损坏：Popen 无 kwargs 时条件表达式恒为 assert True 空转通过，有 kwargs 时 call_kwargs.get 在 unittest.mock._Call 上不存在会抛 AttributeError，声称的“验证不使用 shell=True”从未被真正验证。", "severity": "MEDIUM" },
#{ "file": "tests/test_batch1_regression.py", "issue": "TestMakeResult 的 8 条契约测试作用于本地复制的 _make_result 镜像实现而非真实 server._make_result，真实函数仅 3 条浅断言；server.py 实现语义漂移时镜像测试仍全绿，产生假保障。", "severity": "MEDIUM" },
#{ "file": "tests/test_download_flow.py", "issue": "TestDownloadViaUi 仅对自己 fixture 做 json.loads 往返断言，未调用 download_via_ui 或其解析逻辑；test_gui_running_check 断言 mock 自身 returncode==0。空转断言，无法发现真实解析/检查回归。", "severity": "LOW" },
#{ "file": "tests/test_validator_interlock.py", "issue": "test_heater_cooldown_enforced 依赖真实墙钟，两次 validate 必须落在 5s 冷却窗内，慢 CI/调试暂停时会假失败；同目录 test_robot_safety_rules.py 已用假时钟消除同一竞态，本文件未同步。", "severity": "LOW" },
#{ "file": "tests/test_safety_validator.py", "issue": "test_fuse_trips_on_max_errors 硬编码连续错误数 3 判定熔断，与 env safety_max_consecutive_errors 决定的 _MAX_ERRORS 耦合（默认 3、可配置、非法值回退 1）；环境变量变化时假失败，test_s7_write_safety.py 已改用 validator_module._MAX_ERRORS 消除此耦合。", "severity": "LOW" },
#{ "file": "tests/offline/test_pytest_collection_safety.py", "issue": "离线边界仅验证 -m 过滤不被收集，但默认收集仍会导入 test_robot_mcp.py，其模块级 import 触发 robot-mcp/server.py 执行 get_control_target()/approved_opcua_endpoint() 实时读取校验 config.yaml；config 缺失或漂移时整个离线套件在收集期报错，隔离承诺弱于声明范围。", "severity": "LOW" },
#{ "file": "tests/test_robot_mcp.py", "issue": "test_opcua_connection 用 except Exception 捕获任意异常并 pytest.skip，把被测 server.py 的真实 bug/认证失败与 PLCSIM 未运行混为一谈，真实失败被静默跳过而非报错", "severity": "MEDIUM" },
#{ "file": "tests/test_p3_flow_parsing.py", "issue": "模块级 import p3_flow 用 except Exception 捕获所有异常，p3_flow.py 的 import 期真实 bug（NameError/TypeError）会被当作环境缺依赖而让整个测试类跳过，回归被掩盖；应只捕获 ImportError/ModuleNotFoundError", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/conveyor-with-timer.scl", "issue": "全部 20 个 .scl 模板的 IEC 定时器/边沿实例调用均缺少 _rules.md 第 6/7 条强制要求的 # 前缀（如 tStartDelay(IN:=TRUE,...)、trgEntry(CLK:=...)、tPhaseTimer.IN/PT/ET），与 README 宣称的\"可直接编译\"自相矛盾；scl_lint.py 的 IEC_INSTANCE_WITHOUT_HASH 规则只匹配 TON/R_TRIG 等类型名，tStartDelay 等实例名调用全部漏检，server.py 导入前 lint 无法拦截", "severity": "HIGH" },
#{ "file": "plc-code-templates/siemens-scl/冷冻站群控系统.scl", "issue": "加机选冷机 iNextChiller 未排除已运行的冷机（无 AND NOT bChillerXRun），当最小累计运行时间的冷机正在运行时，bChillerXCmd 重复发给该已运行冷机，新增冷机永远不会收到启动命令，台数控制卡在低于目标值", "severity": "HIGH" },
#{ "file": "plc-code-templates/siemens-scl/冷冻站群控系统.scl", "issue": "主泵启动故障切换只在单个扫描周期把命令切到备泵，下一周期 iPrimaryPump=1 分支重新断言 bChPump1Cmd:=TRUE 并复位 bChPump2Cmd，且切换时不更新 iPrimaryPump，备泵无法真正接管", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/mixer.scl", "issue": "bStop 或故障置 iState:=0 时不复位 tFill/tMix/tDrain，TON 冻结 ET，重新启动后计时从中断处续走而非重新计时，阶段时长被静默缩短（traffic_light/packaging-machine/sbr/cip 同类）", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/tank_level.scl", "issue": "bOverflowAlarm 仅在急停/溢流/干转安全分支被赋值（bOverflowAlarm:=bOverflow），溢流消除后没有任何赋值路径清除它，报警永久锁存", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/智能照明控制.scl", "issue": "iActiveScene 由 iSceneCmd>0 置为 1-6 后永久保持，无任何清除/回落逻辑，CASE 的 ELSE 自动模式分支从此不可达，系统锁死在最后一次场景命令", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/pump-station.scl", "issue": "输入 rRuntimeHours 从未使用，tRotation/iPumpIndex 每 30 分钟递增但对 bRunCmd1-4 无任何影响（死代码），声明的 Duty 轮换阈值和计时器完全失效", "severity": "MEDIUM" },
#{ "file": "plc-code-templates/siemens-scl/停车场管理系统.scl", "issue": "bReset 故障复位直接 iOccupied:=0 清空占用车位计数，满场状态下复位会立即显示空位并放行超额车辆，存在运营安全隐患", "severity": "MEDIUM" }
];

// 分批验证：args.start / args.count 每批最多 128 条。
let batch_start = if args == () { 0 } else { if args.start == () { 0 } else { args.start } };
let batch_count = if args == () { 128 } else { if args.count == () { 128 } else { args.count } };
let batch = [];
let end = batch_start + batch_count;
if end > findings.len() { end = findings.len(); }
let idx = batch_start;
while idx < end { batch.push(findings[idx]); idx += 1; }
log("本批验证范围：findings[" + batch_start.to_string() + " .. " + end.to_string() + ") 共 " + batch.len().to_string() + " 条");

phase("Verify");
let vjobs = [];
for f in batch {
    vjobs.push(#{
        prompt: "对抗性验证下面这条审查发现，必须实际读取代码确认，不能只凭审查者转述。发现：\"" + f.issue + "\"，文件：" + f.file
            + "，声称严重度：" + f.severity + "。只有在你能独立检查到具体证据（如具体行、调用链、配置项）时才设 real=true；"
            + "证据不足、无法复现、描述模糊或文件不存在一律设 real=false，reason 说明理由，evidence 给出你独立看到的证据（含文件与行号）。",
        label: "verify:" + f.file,
        capability_mode: "read-only",
        output_schema: verdict_schema,
    });
}
log("本批派出 " + vjobs.len().to_string() + " 个验证子代理");
let verdicts = parallel(vjobs);

let confirmed = [];
let i = 0;
for v in verdicts {
    if v != () && v.success && v.output.real == true
        && v.output.evidence != () && v.output.evidence != "" {
        confirmed.push(batch[i]);
    }
    i += 1;
}
log(confirmed.len().to_string() + "/" + batch.len().to_string() + " 条发现通过对抗验证");
complete(#{ summary: confirmed.len().to_string() + " 条确认发现（其余已被质疑者驳回）", confirmed: confirmed });
