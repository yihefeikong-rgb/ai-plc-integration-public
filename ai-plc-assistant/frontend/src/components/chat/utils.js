// ChatArea 工具函数
import { exportCode } from '../../api'

export function downloadFile(content, filename, mime = 'text/plain') {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// 容错解析 content：对象直接用，字符串尝试 JSON.parse，失败退化到 {text}
export function parseContent(content) {
  if (content == null) return {}
  if (typeof content === 'string') {
    try {
      const parsed = JSON.parse(content)
      return typeof parsed === 'object' && parsed !== null ? parsed : { text: content }
    } catch {
      return { text: content }
    }
  }
  return content
}

export function formatSize(bytes) {
  if (typeof bytes !== 'number' || bytes < 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export async function handleExport(structured, format, title) {
  try {
    const data = await exportCode({
      title: title || 'export',
      variables: structured.variables || [],
      networks: structured.networks || [],
      format,
      block_type: 'FB',
      block_name: title || 'GeneratedBlock',
    })
    downloadFile(data.content, data.filename, data.mime_type)
  } catch (err) {
    alert('导出失败: ' + err.message)
  }
}
