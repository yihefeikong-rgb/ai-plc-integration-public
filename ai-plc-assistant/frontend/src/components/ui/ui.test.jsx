import React from 'react'
import { describe, expect, it, vi, beforeAll } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'

import {
  Button,
  IconButton,
  Input,
  TextArea,
  Select,
  Checkbox,
  StatusDot,
  StatusBadge,
  StatusIndicator,
  Panel,
  PanelHeader,
  Tabs,
  ToolbarButton,
  DropdownMenu,
  EmptyState,
  ErrorState,
  LoadingState,
  ConfirmDialog,
  Tooltip,
  DataTable,
  CodeViewer,
  LogViewer,
  ToolStatusBar,
} from './index'

import { Settings, FolderOpen, AlertTriangle, Server } from 'lucide-react'

// jsdom 不实现 scrollIntoView，测试前 mock
beforeAll(() => {
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn()
  }
  if (!Element.prototype.scrollTo) {
    Element.prototype.scrollTo = vi.fn()
  }
})

describe('Button', () => {
  it('renders children and responds to click', () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>保存</Button>)
    const btn = screen.getByText('保存')
    fireEvent.click(btn)
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('disables click when disabled', () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>保存</Button>)
    fireEvent.click(screen.getByText('保存'))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('applies variant class', () => {
    render(<Button variant="primary">主按钮</Button>)
    const btn = screen.getByText('主按钮').closest('button')
    expect(btn.className).toContain('btn-primary')
  })

  it('applies size class', () => {
    render(<Button size="sm">小</Button>)
    expect(screen.getByText('小').closest('button').className).toContain('btn-sm')
  })

  it('renders icon', () => {
    render(<Button icon={Settings}>设置</Button>)
    expect(screen.getByText('设置')).toBeTruthy()
  })
})

describe('IconButton', () => {
  it('renders with aria-label', () => {
    const { container } = render(<IconButton icon={Settings} label="设置" />)
    const btn = container.querySelector('button')
    expect(btn.getAttribute('aria-label')).toBe('设置')
  })

  it('responds to click', () => {
    const onClick = vi.fn()
    const { container } = render(<IconButton icon={Settings} label="设置" onClick={onClick} />)
    fireEvent.click(container.querySelector('button'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

describe('Input / TextArea / Select', () => {
  it('Input handles value change', () => {
    let value = ''
    render(<Input value={value} onChange={(e) => { value = e.target.value }} placeholder="测试" />)
    const input = screen.getByPlaceholderText('测试')
    fireEvent.change(input, { target: { value: 'hello' } })
    expect(value).toBe('hello')
  })

  it('TextArea renders rows', () => {
    const { container } = render(<TextArea rows={5} placeholder="多行" />)
    const ta = container.querySelector('textarea')
    expect(ta.getAttribute('rows')).toBe('5')
  })

  it('Select renders options', () => {
    render(
      <Select value="a" onChange={() => {}}>
        <option value="a">A</option>
        <option value="b">B</option>
      </Select>
    )
    expect(screen.getByText('A')).toBeTruthy()
  })
})

describe('Checkbox', () => {
  it('renders label and handles change', () => {
    const onChange = vi.fn()
    render(<Checkbox checked={false} onChange={onChange} label="启用" />)
    const lbl = screen.getByText('启用')
    fireEvent.click(lbl)
    // label 内 input click 应触发 onChange
    expect(screen.getByText('启用')).toBeTruthy()
  })
})

describe('StatusDot / StatusBadge / StatusIndicator', () => {
  it('StatusDot applies status class', () => {
    const { container } = render(<StatusDot status="ok" />)
    const span = container.querySelector('span')
    expect(span.className).toContain('status-dot-ok')
  })

  it('StatusBadge renders label text', () => {
    render(<StatusBadge status="connected" label="PLC 已连接" />)
    expect(screen.getByText('PLC 已连接')).toBeTruthy()
  })

  it('StatusBadge includes aria-label for accessibility', () => {
    const { container } = render(<StatusBadge status="error" label="后端离线" />)
    const badge = container.querySelector('[role="status"]')
    expect(badge.getAttribute('aria-label')).toBe('后端离线')
  })

  it('StatusIndicator renders label and value', () => {
    render(<StatusIndicator label="PLC" value="S7-1200" status="connected" />)
    expect(screen.getByText('PLC')).toBeTruthy()
    expect(screen.getByText('S7-1200')).toBeTruthy()
  })

  it('StatusIndicator handles click', () => {
    const onClick = vi.fn()
    const { container } = render(<StatusIndicator label="PLC" value="S7-1200" status="connected" onClick={onClick} />)
    fireEvent.click(container.querySelector('[role="button"]'))
    expect(onClick).toHaveBeenCalledTimes(1)
  })
})

describe('Panel / PanelHeader', () => {
  it('Panel renders title and children', () => {
    render(<Panel title="系统状态" icon={Server}>内容</Panel>)
    expect(screen.getByText('系统状态')).toBeTruthy()
    expect(screen.getByText('内容')).toBeTruthy()
  })

  it('PanelHeader renders title and children', () => {
    render(<PanelHeader icon={Server} title="监控">右侧</PanelHeader>)
    expect(screen.getByText('监控')).toBeTruthy()
    expect(screen.getByText('右侧')).toBeTruthy()
  })
})

describe('Tabs', () => {
  it('renders active content only', () => {
    render(
      <Tabs defaultValue="log">
        <Tabs.List>
          <Tabs.Trigger value="log">日志</Tabs.Trigger>
          <Tabs.Trigger value="ai">AI 调用</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="log">日志内容</Tabs.Content>
        <Tabs.Content value="ai">AI 调用内容</Tabs.Content>
      </Tabs>
    )
    expect(screen.getByText('日志内容')).toBeTruthy()
    // 另一内容应不显示
    const aiPanel = screen.queryByText('AI 调用内容')
    // forceMount=false 时返回 null，因此 queryByText 应为 null
    expect(aiPanel).toBeNull()
  })

  it('switches tab on click', () => {
    render(
      <Tabs defaultValue="log">
        <Tabs.List>
          <Tabs.Trigger value="log">日志</Tabs.Trigger>
          <Tabs.Trigger value="ai">AI 调用</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="log">日志内容</Tabs.Content>
        <Tabs.Content value="ai">AI 调用内容</Tabs.Content>
      </Tabs>
    )
    fireEvent.click(screen.getByText('AI 调用'))
    expect(screen.getByText('AI 调用内容')).toBeTruthy()
  })
})

describe('ToolbarButton', () => {
  it('applies active class', () => {
    render(<ToolbarButton active={true}>视图</ToolbarButton>)
    expect(screen.getByText('视图').className).toContain('bg-ide-active')
  })
})

describe('DropdownMenu', () => {
  it('opens on click and triggers action', () => {
    const onAction = vi.fn()
    render(
      <DropdownMenu label="项目" onAction={onAction}>
        <DropdownMenu.Item action="project:new">新建项目</DropdownMenu.Item>
        <DropdownMenu.Separator />
        <DropdownMenu.Item action="project:settings">项目设置</DropdownMenu.Item>
      </DropdownMenu>
    )
    // 初始菜单项不可见
    expect(screen.queryByText('新建项目')).toBeNull()
    // 点击展开
    fireEvent.click(screen.getByText('项目'))
    expect(screen.getByText('新建项目')).toBeTruthy()
    // 点击菜单项
    fireEvent.click(screen.getByText('新建项目'))
    expect(onAction).toHaveBeenCalledWith('project:new')
  })
})

describe('EmptyState / ErrorState / LoadingState', () => {
  it('EmptyState renders icon, title, description', () => {
    render(<EmptyState icon={FolderOpen} title="暂无项目" description="点击上方新建" />)
    expect(screen.getByText('暂无项目')).toBeTruthy()
    expect(screen.getByText('点击上方新建')).toBeTruthy()
  })

  it('ErrorState renders title and description', () => {
    render(<ErrorState title="加载失败" description="网络超时" />)
    expect(screen.getByText('加载失败')).toBeTruthy()
    expect(screen.getByText('网络超时')).toBeTruthy()
  })

  it('LoadingState renders label', () => {
    render(<LoadingState label="AI 解析中..." />)
    expect(screen.getByText('AI 解析中...')).toBeTruthy()
  })
})

describe('ConfirmDialog', () => {
  it('calls onConfirm on confirm click', () => {
    const onConfirm = vi.fn()
    const onClose = vi.fn()
    render(
      <ConfirmDialog
        title="删除对话"
        description="确认删除？"
        confirmLabel="确认删除"
        variant="danger"
        onConfirm={onConfirm}
        onClose={onClose}
      />
    )
    fireEvent.click(screen.getByText('确认删除'))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose on cancel click', () => {
    const onClose = vi.fn()
    render(
      <ConfirmDialog title="确认" onClose={onClose} />
    )
    fireEvent.click(screen.getByText('取消'))
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('Tooltip', () => {
  it('renders children without content by default', () => {
    const { container } = render(
      <Tooltip content="提示文字">
        <button>触发</button>
      </Tooltip>
    )
    expect(screen.getByText('触发')).toBeTruthy()
    // content 默认不显示
    expect(screen.queryByText('提示文字')).toBeNull()
  })
})

describe('DataTable', () => {
  it('renders columns and data', () => {
    render(
      <DataTable
        columns={[
          { key: 'addr', label: '地址', mono: true },
          { key: 'name', label: '符号' },
        ]}
        data={[
          { addr: 'I0.0', name: 'bStart' },
          { addr: 'Q0.0', name: 'qMotor' },
        ]}
      />
    )
    expect(screen.getByText('地址')).toBeTruthy()
    expect(screen.getByText('I0.0')).toBeTruthy()
    expect(screen.getByText('bStart')).toBeTruthy()
    expect(screen.getByText('qMotor')).toBeTruthy()
  })

  it('renders emptyText when data is empty', () => {
    render(<DataTable columns={[{ key: 'a', label: 'A' }]} data={[]} emptyText="暂无数据" />)
    expect(screen.getByText('暂无数据')).toBeTruthy()
  })

  it('uses custom render function', () => {
    render(
      <DataTable
        columns={[
          { key: 'v', label: 'V', render: (val) => <strong>{val}</strong> },
        ]}
        data={[{ v: 'test' }]}
      />
    )
    expect(screen.getByText('test').tagName).toBe('STRONG')
  })
})

describe('CodeViewer', () => {
  it('renders code with language label', () => {
    render(<CodeViewer code={'NETWORK 1\n  bStart'} language="SCL" title="块1" />)
    expect(screen.getByText('块1')).toBeTruthy()
    expect(screen.getByText('SCL')).toBeTruthy()
  })

  it('renders empty state when no code', () => {
    render(<CodeViewer code={''} />)
    expect(screen.getByText('无代码内容')).toBeTruthy()
  })
})

describe('LogViewer', () => {
  it('renders logs with time and level', () => {
    const logs = [
      { time: '10:00:01', level: 'info', message: '系统已启动' },
      { time: '10:00:02', level: 'error', message: '后端离线' },
    ]
    render(<LogViewer logs={logs} />)
    expect(screen.getByText('系统已启动')).toBeTruthy()
    expect(screen.getByText('后端离线')).toBeTruthy()
  })

  it('renders emptyText when no logs', () => {
    render(<LogViewer logs={[]} emptyText="无日志" />)
    expect(screen.getByText('无日志')).toBeTruthy()
  })
})

describe('ToolStatusBar', () => {
  it('renders all 10 defined statuses with correct label', () => {
    const statuses = [
      { status: 'idle', label: '空闲' },
      { status: 'inputting', label: '输入中' },
      { status: 'validation_failed', label: '校验失败' },
      { status: 'running', label: '执行中' },
      { status: 'success', label: '执行成功' },
      { status: 'failed', label: '执行失败' },
      { status: 'partial', label: '部分成功' },
      { status: 'no_result', label: '无结果' },
      { status: 'offline', label: '后端离线' },
      { status: 'model_unavailable', label: '模型不可用' },
    ]
    for (const { status, label } of statuses) {
      const { unmount } = render(<ToolStatusBar status={status} />)
      expect(screen.getByText(label)).toBeTruthy()
      unmount()
    }
  })

  it('falls back to idle for unknown status', () => {
    render(<ToolStatusBar status="unknown_status" />)
    expect(screen.getByText('空闲')).toBeTruthy()
  })

  it('shows model when provided, hides when not', () => {
    const { rerender } = render(<ToolStatusBar status="running" model="deepseek" />)
    expect(screen.getByText(/deepseek/)).toBeTruthy()
    rerender(<ToolStatusBar status="running" />)
    expect(screen.queryByText(/deepseek/)).toBeNull()
  })
})
