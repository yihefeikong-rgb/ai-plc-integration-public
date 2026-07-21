// 梯形图生成结果消息 — 含变量表、网络、导出按钮
import { useState } from 'react'
import {
  Download, FileCode, FileText as FileXml, Table2, Eye, Code,
} from 'lucide-react'
import LadderVisualizer from '../../LadderVisualizer'
import { handleExport } from '../utils'

export default function LadderResult({ msg }) {
  const { title, description, structured } = msg
  const { variables, networks } = structured || {}
  // F-026 修复：ASCII-LAD 默认显示（textMode=true），SVG 不再默认
  const [textMode, setTextMode] = useState(true)

  return (
    <div className="space-y-3">
      <div className="text-sm font-medium text-accent">{title}</div>
      {description && <div className="text-2xs text-text-dim">{description}</div>}

      {variables?.length > 0 && (
        <div>
          <div className="text-2xs font-medium text-text-secondary mb-1 uppercase tracking-wider">变量表</div>
          <div className="overflow-x-auto border border-ide-border rounded">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ide-panel text-text-dim border-b border-ide-border">
                  <th className="text-left px-3 py-1.5">地址</th>
                  <th className="text-left px-3 py-1.5">符号</th>
                  <th className="text-left px-3 py-1.5">类型</th>
                  <th className="text-left px-3 py-1.5">注释</th>
                </tr>
              </thead>
              <tbody>
                {variables.map((v, i) => (
                  <tr key={v.address || v.name || i} className="border-b border-ide-border last:border-0 text-text-secondary">
                    <td className="px-3 py-1 font-mono text-accent">{v.address}</td>
                    <td className="px-3 py-1 font-mono">{v.name}</td>
                    <td className="px-3 py-1">{v.data_type}</td>
                    <td className="px-3 py-1 text-text-dim">{v.comment}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {networks?.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-2xs font-medium text-text-secondary uppercase tracking-wider">程序逻辑</div>
            <button
              type="button"
              onClick={() => setTextMode(!textMode)}
              className="flex items-center gap-1 px-2 py-0.5 text-2xs text-text-dim hover:text-accent border border-transparent hover:border-accent/40 rounded transition-colors"
              title={textMode ? '显示图形' : '显示源码'}
            >
              {textMode ? <Eye size={12} /> : <Code size={12} />}
              {textMode ? '图形' : '源码'}
            </button>
          </div>
          {networks.map((n, i) => (
            <div key={n.number || i} className="border border-ide-border rounded overflow-hidden">
              <div className="px-3 py-1.5 bg-ide-panel border-b border-ide-border flex items-center gap-2">
                <span className="text-2xs font-mono text-accent">Network {n.number}</span>
                <span className="text-xs text-text-primary">{n.title}</span>
              </div>
              {n.comment && (
                <div className="px-3 py-1 text-2xs text-text-dim border-b border-ide-border">
                  // {n.comment}
                </div>
              )}
              {n.code && textMode && (
                <pre className="px-3 py-2 text-xs text-text-secondary font-mono leading-relaxed overflow-x-auto bg-ide-panel">
                  {n.code}
                </pre>
              )}
              {n.code && !textMode && (
                <LadderVisualizer networks={[n]} />
              )}
            </div>
          ))}
        </div>
      )}

      {structured && (
        <div className="flex items-center gap-2 pt-2 border-t border-ide-border">
          <span className="text-2xs text-text-dim mr-1">导出:</span>
          <button type="button" onClick={() => handleExport(structured, 'scl', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileCode size={12} /> SCL
          </button>
          <button type="button" onClick={() => handleExport(structured, 'xml', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <FileXml size={12} /> XML
          </button>
          <button type="button" onClick={() => handleExport(structured, 'csv', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Table2 size={12} /> CSV
          </button>
          <button type="button" onClick={() => handleExport(structured, 'hmi', title)}
            className="flex items-center gap-1 px-2.5 py-1 text-2xs bg-ide-panel border border-ide-border rounded hover:border-accent/40 hover:text-accent transition-colors text-text-secondary">
            <Download size={12} /> HMI
          </button>
        </div>
      )}
    </div>
  )
}
