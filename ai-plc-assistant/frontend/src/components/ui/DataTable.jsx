import React from 'react'

/**
 * DataTable — 数据表格
 *
 * 用法：
 *   <DataTable
 *     columns={[{key:'addr',label:'地址'},{key:'name',label:'符号'}]}
 *     data={[{addr:'I0.0',name:'bStart'}, ...]}
 *     emptyText="暂无数据"
 *   />
 *
 * 列定义可选字段：
 *   key, label, render(value, row, index), className, width, mono, align
 */
export default function DataTable({
  columns,
  data = [],
  emptyText = '暂无数据',
  className = '',
  rowKey = (row, i) => row.id || i,
  onRowClick,
  dense = false,
}) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center text-text-dim text-xs py-6">{emptyText}</div>
    )
  }
  return (
    <div className={`overflow-x-auto border border-ide-border rounded ${className}`}>
      <table className="w-full text-xs" role="table">
        <thead>
          <tr className="bg-ide-panel text-text-dim border-b border-ide-border">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`text-left px-3 ${dense ? 'py-1' : 'py-1.5'} ${
                  col.mono ? 'font-mono' : ''
                } ${col.className || ''}`}
                style={{ width: col.width, textAlign: col.align || 'left' }}
                scope="col"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={rowKey(row, i)}
              onClick={onRowClick ? () => onRowClick(row, i) : undefined}
              className={`border-b border-ide-border last:border-0 text-text-secondary ${
                onRowClick ? 'cursor-pointer hover:bg-ide-hover' : ''
              }`}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`px-3 ${dense ? 'py-1' : 'py-1.5'} ${
                    col.mono ? 'font-mono' : ''
                  } ${col.cellClassName || ''}`}
                  style={{ textAlign: col.align || 'left' }}
                >
                  {col.render ? col.render(row[col.key], row, i) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
