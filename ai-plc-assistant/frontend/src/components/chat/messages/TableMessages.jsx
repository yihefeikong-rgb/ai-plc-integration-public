// IO 表 + 变量表消息 — 用 DataTable 渲染
import { Table2, AtSign } from 'lucide-react'
import { DataTable } from '../../ui'
import { parseContent } from '../utils'
import { MSG_TYPES } from '../constants'
import PlaceholderMessage from './PlaceholderMessage'

// D-1：IO 表消息 — 用 DataTable 渲染设备 IO 地址表
export function IoTableMessage({ content }) {
  const data = parseContent(content)
  const rows = data.rows || data.io || data.devices || []
  if (!rows.length) return <PlaceholderMessage type={MSG_TYPES.IO_TABLE} content={content} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-2xs text-text-dim uppercase tracking-wider">
        <Table2 size={12} /> IO 地址表 ({rows.length})
      </div>
      <DataTable
        columns={[
          { key: 'address', label: '地址', mono: true },
          { key: 'name', label: '符号', mono: true },
          { key: 'type', label: '类型' },
          { key: 'direction', label: '方向' },
          { key: 'comment', label: '注释' },
        ]}
        data={rows}
        rowKey={(row, i) => row.address || row.name || i}
        emptyText="无 IO 数据"
        dense
      />
    </div>
  )
}

// D-1：变量表消息 — 用 DataTable 渲染变量分析结果
export function VariablesMessage({ content }) {
  const data = parseContent(content)
  const rows = data.variables || data.rows || data.vars || []
  if (!rows.length) return <PlaceholderMessage type={MSG_TYPES.VARIABLES} content={content} />
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-2xs text-text-dim uppercase tracking-wider">
        <AtSign size={12} /> 变量分析 ({rows.length})
      </div>
      <DataTable
        columns={[
          { key: 'address', label: '地址', mono: true },
          { key: 'name', label: '符号', mono: true },
          { key: 'data_type', label: '类型' },
          { key: 'usage', label: '用法' },
          { key: 'comment', label: '注释' },
        ]}
        data={rows}
        rowKey={(row, i) => row.address || row.name || i}
        emptyText="无变量数据"
        dense
      />
    </div>
  )
}
