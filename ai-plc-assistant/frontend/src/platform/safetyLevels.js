/**
 * 安全等级定义（Batch 8，主计划 §11.5）
 *
 * Level 0：只读 — 仅查看，不写入
 * Level 1：本地写入 — 本地工程修改，不影响实机
 * Level 2：工程修改 — 修改 TIA Portal 工程
 * Level 3：设备控制 — 写入实机 PLC，高风险
 *
 * 高风险操作（Level 3）必须显示：
 * 操作名称/目标 PLC/IP/型号/当前项目/运行状态/影响范围/可回滚/风险说明
 */

export const SAFETY_LEVELS = {
  LEVEL_0_READONLY: {
    level: 0,
    id: 'readonly',
    label: '只读',
    description: '仅查看，不写入',
    tone: 'readonly',
  },
  LEVEL_1_LOCAL_WRITE: {
    level: 1,
    id: 'local-write',
    label: '本地写入',
    description: '本地工程修改，不影响实机',
    tone: 'neutral',
  },
  LEVEL_2_PROJECT_MODIFY: {
    level: 2,
    id: 'project-modify',
    label: '工程修改',
    description: '修改 TIA Portal 工程',
    tone: 'warning',
  },
  LEVEL_3_DEVICE_CONTROL: {
    level: 3,
    id: 'device-control',
    label: '设备控制',
    description: '写入实机 PLC，高风险',
    tone: 'danger',
  },
}

export const DEFAULT_SAFETY_LEVEL = SAFETY_LEVELS.LEVEL_0_READONLY

/**
 * 高风险操作确认所需字段（主计划 §11.5）
 */
export const HIGH_RISK_CONFIRM_FIELDS = [
  'operation',      // 操作名称
  'targetPlc',      // 目标 PLC
  'ipAddress',      // IP 地址
  'plcModel',       // PLC 型号
  'currentProject', // 当前项目
  'runState',       // 当前运行状态
  'impactScope',    // 影响范围
  'rollbackable',   // 是否可回滚
  'riskNotes',      // 风险说明
]

/**
 * 危险按钮具体文案模板（主计划 §11.5）
 */
export const DANGER_BUTTON_LABELS = {
  STOP_CPU: '确认停止 CPU',
  DOWNLOAD_TO_PLC: '确认下载到 PLC',
  OVERWRITE_BLOCK: '确认覆盖程序块',
  WRITE_VARIABLE: '确认写入变量',
}
