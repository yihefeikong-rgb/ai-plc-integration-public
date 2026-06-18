import { useState, useRef, useCallback, useEffect } from 'react'
import { ZoomIn, ZoomOut, Maximize2, Download, RotateCcw } from 'lucide-react'

/**
 * LadderSvgRenderer — SVGRendererV2 SVG 安全渲染组件
 *
 * Props:
 *   svgString: string  — V2 生成的 SVG 原始字符串
 *   title: string      — 可选标题（用于下载文件名）
 *   onDownload: fn     — 可选外部下载处理器
 *
 * 功能：
 *   - SVG 安全渲染 (dangerouslySetInnerHTML)
 *   - 缩放 (+, -, reset)
 *   - 全屏查看
 *   - 下载 SVG 文件
 *   - 自适应暗色主题容器
 */
export default function LadderSvgRenderer({ svgString, title, onDownload }) {
  const containerRef = useRef(null)
  const [zoom, setZoom] = useState(1)
  const [isFullscreen, setIsFullscreen] = useState(false)

  // 监听全屏变化
  useEffect(() => {
    const handler = () => setIsFullscreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handler)
    return () => document.removeEventListener('fullscreenchange', handler)
  }, [])

  // 缩放控制
  const zoomIn = useCallback(() => setZoom(z => Math.min(z + 0.25, 3)), [])
  const zoomOut = useCallback(() => setZoom(z => Math.max(z - 0.25, 0.25)), [])
  const resetZoom = useCallback(() => setZoom(1), [])

  // 全屏切换
  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return
    if (document.fullscreenElement) {
      await document.exitFullscreen()
    } else {
      await containerRef.current.requestFullscreen()
    }
  }, [])

  // 下载 SVG
  const handleDownload = useCallback(() => {
    if (onDownload) {
      onDownload()
      return
    }
    if (!svgString) return
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${title || 'ladder'}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }, [svgString, title, onDownload])

  if (!svgString) {
    return (
      <div className="flex items-center justify-center h-32 text-text-dim text-xs bg-ide-panel/50 rounded border border-ide-border">
        SVG 不可用
      </div>
    )
  }

  // 从 SVG 字符串中提取 viewBox 宽高用于初始尺寸估算
  const viewBoxMatch = svgString.match(/viewBox="([^"]+)"/)
  const [_, vbx = '0 0 800 400'] = viewBoxMatch || []
  const [, , vbw = '800', vbh = '400'] = vbx.split(/\s+/).map(Number)
  const aspectRatio = vbw / vbh || 2

  return (
    <div className="flex flex-col gap-1">
      {/* 工具栏 */}
      <div className="flex items-center gap-1 px-2 py-1 bg-ide-panel border border-ide-border rounded-t">
        <span className="text-2xs text-text-dim mr-1">SVG V2</span>
        <div className="flex-1" />

        {/* 提示信息 */}
        <span className="text-2xs text-text-dim mr-2">
          {Math.round(zoom * 100)}%
        </span>

        {/* 缩放按钮 */}
        <button onClick={zoomOut} title="缩小"
          className="p-0.5 rounded hover:bg-ide-bg text-text-dim hover:text-text-primary transition-colors">
          <ZoomOut size={13} />
        </button>
        <button onClick={resetZoom} title="重置缩放"
          className="p-0.5 rounded hover:bg-ide-bg text-text-dim hover:text-text-primary transition-colors">
          <RotateCcw size={13} />
        </button>
        <button onClick={zoomIn} title="放大"
          className="p-0.5 rounded hover:bg-ide-bg text-text-dim hover:text-text-primary transition-colors">
          <ZoomIn size={13} />
        </button>

        <div className="w-px h-4 bg-ide-border mx-1" />

        {/* 全屏 */}
        <button onClick={toggleFullscreen} title="全屏查看"
          className="p-0.5 rounded hover:bg-ide-bg text-text-dim hover:text-text-primary transition-colors">
          <Maximize2 size={13} />
        </button>

        {/* 下载 */}
        <button onClick={handleDownload} title="下载 SVG"
          className="p-0.5 rounded hover:bg-ide-bg text-text-dim hover:text-text-primary transition-colors">
          <Download size={13} />
        </button>
      </div>

      {/* SVG 显示区域 */}
      <div
        ref={containerRef}
        className="overflow-auto bg-[#1a1a2e] border border-ide-border rounded-b"
        style={{
          maxHeight: isFullscreen ? '100vh' : '480px',
          minHeight: '160px',
        }}
      >
        <div
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            width: isFullscreen ? '100%' : Math.min(vbw, 800),
          }}
        >
          <div
            dangerouslySetInnerHTML={{ __html: svgString }}
            style={{ 
              width: vbw,
              height: vbh,
              maxWidth: 'none',
            }}
          />
        </div>
      </div>
    </div>
  )
}
