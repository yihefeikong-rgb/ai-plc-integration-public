import { useState, useRef, useEffect } from 'react'
import { Cpu, Circle } from 'lucide-react'
import DropdownMenu from '../components/ui/DropdownMenu'

/**
 * MenuBar — 顶部菜单栏（从 Toolbar.jsx 迁移，去除模型选择器与重复入口）
 *
 * 保留菜单：项目 / 编辑 / 工具 / AI / 视图 / 帮助
 * 去除与 Sidebar/Dashboard 重复的入口：梯形图/解析/IO表/诊断/变量分析（在 Sidebar 工作区分组）
 * "关于"弹窗内部 state
 */

const menuConfig = [
  {
    label: '项目',
    items: [
      { label: '新建项目', action: 'project:new', shortcut: 'Ctrl+N' },
      { label: '导入工程', action: 'project:import' },
      { separator: true },
      { label: '项目设置', action: 'project:settings' },
    ],
  },
  {
    label: '编辑',
    items: [
      { label: '撤销', action: 'edit:undo', shortcut: 'Ctrl+Z', disabled: true },
      { label: '重做', action: 'edit:redo', shortcut: 'Ctrl+Y', disabled: true },
      { separator: true },
      { label: '剪切', action: 'edit:cut', shortcut: 'Ctrl+X', disabled: true },
      { label: '复制', action: 'edit:copy', shortcut: 'Ctrl+C', disabled: true },
      { label: '粘贴', action: 'edit:paste', shortcut: 'Ctrl+V', disabled: true },
    ],
  },
  {
    label: '工具',
    items: [
      { label: '工程搜索', action: 'tool:search' },
      { label: '索引当前工程', action: 'tool:index' },
    ],
  },
  {
    label: 'AI',
    items: [
      { label: '新建对话', action: 'ai:new-chat' },
      { separator: true },
      { label: '模板库', action: 'ai:templates' },
      { label: '知识库管理', action: 'ai:knowledge' },
    ],
  },
  {
    label: '视图',
    items: [
      { label: '切换侧栏', action: 'view:sidebar', shortcut: 'Ctrl+B' },
      { label: '切换右面板', action: 'view:context', shortcut: 'Ctrl+J' },
      { label: '切换底部面板', action: 'view:bottom', shortcut: 'Ctrl+`' },
    ],
  },
  {
    label: '帮助',
    items: [
      { label: '编排管理教程', action: 'help:orchestrator-tutorial' },
      { label: '关于 AI PLC Assistant', action: 'help:about' },
      { label: 'API 文档', action: 'help:api-docs' },
    ],
  },
]

export default function MenuBar({ onMenuAction }) {
  return (
    <div className="flex items-center gap-0.5">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-3 pr-3 border-r border-ide-border">
        <Cpu size={18} className="text-accent" />
        <span className="text-text-primary text-xs font-semibold tracking-wide">AI PLC</span>
      </div>

      {/* Menus */}
      {menuConfig.map((menu) => (
        <DropdownMenu
          key={menu.label}
          label={menu.label}
          items={menu.items}
          onAction={onMenuAction}
        />
      ))}
    </div>
  )
}
