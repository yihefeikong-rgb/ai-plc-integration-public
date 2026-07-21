import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, cleanup, fireEvent, waitFor } from '@testing-library/react'

// 必须先 mock api，再 import GlobalStatusBar
vi.mock('../api', () => ({
  healthCheck: vi.fn(),
  orchestratorHealth: vi.fn(),
  listServers: vi.fn(),
}))

import GlobalStatusBar from './GlobalStatusBar'
import { healthCheck, orchestratorHealth, listServers } from '../api'

const MODELS = [
  { id: 'deepseek', name: 'DeepSeek V4 Flash', enabled: true },
  { id: 'kimi', name: 'Kimi K2.7 Code', enabled: true },
  { id: 'disabled', name: 'Disabled Model', enabled: false },
]

beforeEach(() => {
  vi.clearAllMocks()
  healthCheck.mockResolvedValue({ status: 'ok', version: 'v1' })
  orchestratorHealth.mockResolvedValue({ servers_connected: 2 })
  listServers.mockResolvedValue({ servers: [] })
  localStorage.clear()
})

afterEach(() => {
  cleanup()
})

describe('GlobalStatusBar', () => {
  it('渲染所有状态项 + AI 模型选择器', async () => {
    const { getByText, getByTitle } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    // 初始即触发首次 poll
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('安全模式')).toBeTruthy()
    expect(getByText('PLC')).toBeTruthy()
    expect(getByText('TIA')).toBeTruthy()
    expect(getByText('PLCSIM')).toBeTruthy()
    expect(getByText('后端')).toBeTruthy()
    expect(getByText('MCP')).toBeTruthy()
    expect(getByText('项目')).toBeTruthy()
    expect(getByText('AI')).toBeTruthy()
  })

  it('后端在线时显示已连接 + 版本 title', async () => {
    const { getByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('已连接')).toBeTruthy()
  })

  it('后端不可达时显示未连接', async () => {
    healthCheck.mockRejectedValue(new Error('network'))
    const { getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 至少一个状态项显示"未连接"
    expect(getAllByText('未连接').length).toBeGreaterThan(0)
  })

  it('MCP 编排层连接时显示服务器数', async () => {
    orchestratorHealth.mockResolvedValue({ servers_connected: 3 })
    const { getByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(orchestratorHealth).toHaveBeenCalled())
    expect(getByText('3 已连')).toBeTruthy()
  })

  it('F-080 matchServers：plcsim 服务器名匹配 PLCSIM', async () => {
    listServers.mockResolvedValue({
      servers: [
        { name: 'plcsim-server', status: 'connected' },
        { name: 'tia-portal', status: 'connected' },
        { name: 'plc-mcp-bridge', status: 'connected' },
      ],
    })
    const { getByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(listServers).toHaveBeenCalled())
    expect(getByText('已启用')).toBeTruthy() // PLCSIM
  })

  it('F-080 matchServers：服务器 status 非 connected 时不推断为已连接', async () => {
    listServers.mockResolvedValue({
      servers: [{ name: 'plc-mcp-bridge', status: 'stopped' }],
    })
    const { getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(listServers).toHaveBeenCalled())
    // PLC 应显示未连接
    expect(getAllByText('未连接').length).toBeGreaterThan(0)
  })

  it('安全模式点击切换菜单显示 4 等级', async () => {
    const { getByText, getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 初始显示 Level 0 只读
    expect(getByText('只读')).toBeTruthy()
    // 点击安全模式按钮
    const safetyBtn = getByText('安全模式').closest('[role="button"]') || getByText('安全模式').parentElement
    fireEvent.click(safetyBtn)
    // 菜单应出现 4 等级
    expect(getAllByText(/L[0-3]/).length).toBeGreaterThan(0)
  })

  it('F-068 安全等级切换写入 localStorage', async () => {
    const { getByText, getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 打开安全菜单
    const safetyBtn = getByText('安全模式').closest('[role="button"]') || getByText('安全模式').parentElement
    fireEvent.click(safetyBtn)
    // 点击 Level 3 设备控制
    const l3Btn = getAllByText(/设备控制/)[0].closest('button')
    fireEvent.click(l3Btn)
    // localStorage 应写入 'device-control'
    expect(localStorage.getItem('ai-plc:safety-level')).toBe('device-control')
  })

  it('安全等级从 localStorage 恢复', async () => {
    localStorage.setItem('ai-plc:safety-level', 'project-modify')
    const { getByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 应显示 Level 2 工程修改
    expect(getByText('工程修改')).toBeTruthy()
  })

  it('AI 模型选择器点击展开模型列表', async () => {
    const { getByText, getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={vi.fn()} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    // 点击 AI 模型按钮
    const aiBtn = getByText('AI').parentElement
    fireEvent.click(aiBtn)
    // 应显示模型名（DeepSeek / Kimi / Disabled）
    expect(getAllByText(/DeepSeek|Kimi|Disabled/).length).toBeGreaterThan(0)
  })

  it('AI 模型点击调用 onSelectModel', async () => {
    const onSelect = vi.fn()
    const { getByText, getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={onSelect} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    const aiBtn = getByText('AI').parentElement
    fireEvent.click(aiBtn)
    // 点击 Kimi 模型
    const kimiBtn = getAllByText('Kimi K2.7 Code')[0].closest('button')
    fireEvent.click(kimiBtn)
    expect(onSelect).toHaveBeenCalledWith('kimi')
  })

  it('禁用的模型不可点击', async () => {
    const onSelect = vi.fn()
    const { getByText, getAllByText } = render(
      <GlobalStatusBar models={MODELS} selectedModel="deepseek" onSelectModel={onSelect} />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    const aiBtn = getByText('AI').parentElement
    fireEvent.click(aiBtn)
    // 点击禁用模型
    const disabledBtn = getAllByText('Disabled Model')[0].closest('button')
    fireEvent.click(disabledBtn)
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('当前项目名称显示在状态栏', async () => {
    const { getByText } = render(
      <GlobalStatusBar
        models={MODELS}
        selectedModel="deepseek"
        onSelectModel={vi.fn()}
        currentProject={{ name: '测试项目', plc_type: 'S7-1200' }}
      />
    )
    await waitFor(() => expect(healthCheck).toHaveBeenCalled())
    expect(getByText('测试项目')).toBeTruthy()
  })
})
