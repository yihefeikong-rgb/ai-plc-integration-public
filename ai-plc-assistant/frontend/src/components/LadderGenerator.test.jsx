import React from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import LadderGenerator from './LadderGenerator'
import { runNlToSim } from '../api'

vi.mock('../hooks/useWorkbenchHistory', () => ({
  default: () => ({ history: [], save: vi.fn() }),
}))

vi.mock('./LadderVisualizer', () => ({
  default: () => <div data-testid="ladder-visualizer" />,
}))

vi.mock('../api', () => ({
  generateLadder: vi.fn(),
  exportCode: vi.fn(),
  runNlToSim: vi.fn(),
}))

describe('LadderGenerator pipeline entry', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('runs unified simulation pipeline and renders step status', async () => {
    runNlToSim.mockResolvedValue({
      ok: true,
      workflow_name: 'nl_to_plcsim_pipeline',
      steps: [
        { name: '生成梯形图块', status: 'PASS', detail: { blockName: 'MotorFwdRev' }, duration_ms: 10 },
        { name: 'snap7 回读验证', status: 'PASS', detail: 'M0.0 = False', duration_ms: 3 },
      ],
      snap7: { verified: true, readback: 'M0.0 = False' },
      generation: { block_name: 'MotorFwdRev', networks: 3 },
    })

    render(<LadderGenerator addLog={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText(/描述控制需求/), {
      target: { value: '三相异步电机正反转带急停和过载保护' },
    })
    fireEvent.click(screen.getByRole('button', { name: /生成并仿真/ }))

    await waitFor(() => expect(runNlToSim).toHaveBeenCalledWith({
      description: '三相异步电机正反转带急停和过载保护',
      launch_fio: false,
    }))
    expect(await screen.findByText('生成梯形图块')).toBeTruthy()
    expect(screen.getByText('snap7 回读验证')).toBeTruthy()
    expect(screen.getAllByText(/M0.0 = False/).length).toBeGreaterThan(0)
  })

  it('renders pipeline failure message', async () => {
    runNlToSim.mockResolvedValue({
      ok: false,
      error: '编译失败。下一步: 检查 TIA 编译错误',
      steps: [{ name: '编译 TIA 项目', status: 'FAIL', detail: '2 errors', duration_ms: 8 }],
      snap7: { verified: false, readback: '' },
      generation: {},
    })

    render(<LadderGenerator addLog={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText(/描述控制需求/), {
      target: { value: '三相异步电机正反转带急停和过载保护' },
    })
    fireEvent.click(screen.getByRole('button', { name: /生成并仿真/ }))

    expect(await screen.findByText(/编译失败/)).toBeTruthy()
    expect(screen.getByText('编译 TIA 项目')).toBeTruthy()
  })
})
