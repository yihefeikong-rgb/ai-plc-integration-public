// CODE 类型消息 — 用 CodeViewer 渲染（语法高亮 + 复制按钮）
import { CodeViewer } from '../../ui'
import { parseContent } from '../utils'
import { MSG_TYPES } from '../constants'
import PlaceholderMessage from './PlaceholderMessage'

// F-041：CODE 类型独立分发，用 CodeViewer 渲染（语法高亮 + 复制按钮）
export default function CodeMessage({ content }) {
  const data = parseContent(content)
  const code = data.code || data.content || data.text || ''
  const language = data.language || 'SCL'
  const title = data.title
  if (!code) return <PlaceholderMessage type={MSG_TYPES.TOOL_CALL} content={content} />
  return <CodeViewer code={code} language={language} title={title} />
}
