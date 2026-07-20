import { describe, expect, it } from 'vitest'
import {
  SAFETY_LEVELS,
  DEFAULT_SAFETY_LEVEL,
  HIGH_RISK_CONFIRM_FIELDS,
  DANGER_BUTTON_LABELS,
} from './safetyLevels'

describe('safetyLevels', () => {
  it('defines 4 safety levels (0-3)', () => {
    expect(SAFETY_LEVELS.LEVEL_0_READONLY.level).toBe(0)
    expect(SAFETY_LEVELS.LEVEL_1_LOCAL_WRITE.level).toBe(1)
    expect(SAFETY_LEVELS.LEVEL_2_PROJECT_MODIFY.level).toBe(2)
    expect(SAFETY_LEVELS.LEVEL_3_DEVICE_CONTROL.level).toBe(3)
  })

  it('each level has id/label/description/tone', () => {
    for (const key of Object.keys(SAFETY_LEVELS)) {
      const lvl = SAFETY_LEVELS[key]
      expect(lvl.id).toBeTruthy()
      expect(lvl.label).toBeTruthy()
      expect(lvl.description).toBeTruthy()
      expect(lvl.tone).toBeTruthy()
    }
  })

  it('default safety level is LEVEL_0_READONLY', () => {
    expect(DEFAULT_SAFETY_LEVEL.level).toBe(0)
    expect(DEFAULT_SAFETY_LEVEL.id).toBe('readonly')
  })

  it('HIGH_RISK_CONFIRM_FIELDS has 9 fields per master plan §11.5', () => {
    expect(HIGH_RISK_CONFIRM_FIELDS).toHaveLength(9)
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('operation')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('targetPlc')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('ipAddress')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('plcModel')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('currentProject')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('runState')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('impactScope')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('rollbackable')
    expect(HIGH_RISK_CONFIRM_FIELDS).toContain('riskNotes')
  })

  it('DANGER_BUTTON_LABELS has 4 specific labels per master plan §11.5', () => {
    expect(DANGER_BUTTON_LABELS.STOP_CPU).toBe('确认停止 CPU')
    expect(DANGER_BUTTON_LABELS.DOWNLOAD_TO_PLC).toBe('确认下载到 PLC')
    expect(DANGER_BUTTON_LABELS.OVERWRITE_BLOCK).toBe('确认覆盖程序块')
    expect(DANGER_BUTTON_LABELS.WRITE_VARIABLE).toBe('确认写入变量')
  })
})
