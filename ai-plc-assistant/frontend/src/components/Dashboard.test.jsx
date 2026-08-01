import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, fireEvent, waitFor, act } from '@testing-library/react'

vi.mock('../api', () => ({
  listProjects: vi.fn(),
  listConversations: vi.fn(),
  healthCheck: vi.fn(),
  orchestratorHealth: vi.fn(),
  listServers: vi.fn(),
}))

import Dashboard from './Dashboard'
import {
  listProjects, listConversations, healthCheck, orchestratorHealth, listServers,
} from '../api'

beforeEach(() => {
  vi.clearAllMocks()
  listProjects.mockResolvedValue({ projects: [] })
  listConversations.mockResolvedValue({ conversations: [] })
  healthCheck.mockResolvedValue({ status: 'ok' })
  orchestratorHealth.mockResolvedValue({ servers_connected: 0 })
  listServers.mockResolvedValue({ servers: [] })
  localStorage.clear()
})

afterEach(() => {
  cleanup()
})

function renderDashboard(overrides = {}) {
  return render(
    <Dashboard
      onOpenTab={vi.fn()}
      onCreateProject={vi.fn()}
      onImportProject={vi.fn()}
      onNewConversation={vi.fn()}
      currentProject={null}
      conversations={[]}
      onSwitchConversation={vi.fn()}
      {...overrides}
    />
  )
}

describe('Dashboard 全局状态', () => {
  it('后端在线时显示"在线"', async () => {
    healthCheck.mockResolvedValue({ status: 'ok' })
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('在线')).toBeTruthy()
  })

  it('后端不可达时显示"未连接"', async () => {
    healthCheck.mockRejectedValue(new Error('net'))
    const { getAllByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getAllByText('未连接').length).toBeGreaterThan(0)
  })

  it('F-067 PLC 状态从 listServers 推断（plc-mcp-bridge connected）', async () => {
    listServers.mockResolvedValue({
      servers: [{ name: 'plc-mcp-bridge', status: 'connected' }],
    })
    const { getByText } = renderDashboard()
    await waitFor(() => expect(listServers).toHaveBeenCalled())
    // PLC 应显示"已连接"
    expect(getByText('已连接')).toBeTruthy()
  })

  it('F-067 TIA 状态从 listServers 推断', async () => {
    listServers.mockResolvedValue({
      servers: [{ name: 'tia-portal-mcp', status: 'connected' }],
    })
    const { getByText } = renderDashboard()
    await waitFor(() => expect(listServers).toHaveBeenCalled())
    expect(getByText('已启动')).toBeTruthy()
  })

  it('F-067 PLCSIM 状态从 listServers 推断', async () => {
    listServers.mockResolvedValue({
      servers: [{ name: 'plcsim-server', status: 'connected' }],
    })
    const { getByText } = renderDashboard()
    await waitFor(() => expect(listServers).toHaveBeenCalled())
    expect(getByText('已启用')).toBeTruthy()
  })

  it('MCP 编排层连接时显示服务器数', async () => {
    orchestratorHealth.mockResolvedValue({ servers_connected: 5 })
    const { getByText } = renderDashboard()
    await waitFor(() => expect(orchestratorHealth).toHaveBeenCalled())
    expect(getByText('5 已连')).toBeTruthy()
  })

  it('当前项目名称显示在全局状态', async () => {
    const { getAllByText } = renderDashboard({
      currentProject: { name: '电机控制项目', plc_type: 'S7-1200' },
    })
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 项目名在全局状态 + 继续工作区域都出现
    expect(getAllByText('电机控制项目').length).toBeGreaterThanOrEqual(1)
  })
})

describe('Dashboard F-068 安全模式', () => {
  it('默认安全模式为 Level 0 只读', async () => {
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('只读')).toBeTruthy()
  })

  it('F-068 从 localStorage 恢复 Level 2 工程修改', async () => {
    localStorage.setItem('ai-plc:safety-level', 'project-modify')
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('工程修改')).toBeTruthy()
  })

  it('F-068 从 localStorage 恢复 Level 3 设备控制', async () => {
    localStorage.setItem('ai-plc:safety-level', 'device-control')
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('设备控制')).toBeTruthy()
  })

  it('F-068 localStorage 无效值时 fallback 到 Level 0', async () => {
    localStorage.setItem('ai-plc:safety-level', 'invalid-level')
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('只读')).toBeTruthy()
  })

  it('F-068a Level 2 安全模式 StatusRow 使用 text-status-warn 桶位', async () => {
    localStorage.setItem('ai-plc:safety-level', 'project-modify')
    const { getByText, container } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    const safetyValue = getByText('工程修改')
    expect(safetyValue).toBeTruthy()
    // 验证 tone='warning' 映射到 text-status-warn（F-068a 修复的色板桶位）
    expect(safetyValue.className).toContain('text-status-warn')
  })

  it('F-068a Level 3 安全模式 StatusRow 使用 text-status-danger 桶位', async () => {
    localStorage.setItem('ai-plc:safety-level', 'device-control')
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    const safetyValue = getByText('设备控制')
    expect(safetyValue).toBeTruthy()
    // Level 3 tone='danger' 映射到 text-status-danger
    expect(safetyValue.className).toContain('text-status-danger')
  })

  it('F-068a Level 1 安全模式 StatusRow 使用 text-text-secondary（neutral）', async () => {
    localStorage.setItem('ai-plc:safety-level', 'local-write')
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    const safetyValue = getByText('本地写入')
    expect(safetyValue).toBeTruthy()
    // Level 1 tone='neutral' 映射到 text-text-secondary
    expect(safetyValue.className).toContain('text-text-secondary')
  })

  it('F-068 storage 事件触发时同步刷新安全等级', async () => {
    const { getByText } = renderDashboard()
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 初始显示 Level 0
    expect(getByText('只读')).toBeTruthy()
    // 模拟 GlobalStatusBar 切换等级写入 localStorage 并触发 storage 事件
    localStorage.setItem('ai-plc:safety-level', 'project-modify')
    act(() => {
      window.dispatchEvent(new StorageEvent('storage', {
        key: 'ai-plc:safety-level',
        newValue: 'project-modify',
      }))
    })
    // 应更新为 Level 2
    await waitFor(() => expect(getByText('工程修改')).toBeTruthy())
  })
})
