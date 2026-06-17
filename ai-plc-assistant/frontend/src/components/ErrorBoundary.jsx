import { Component } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full flex items-center justify-center bg-ide-bg">
          <div className="max-w-md text-center p-8">
            <AlertTriangle size={40} className="text-status-error mx-auto mb-4" />
            <h2 className="text-sm font-semibold text-text-bright mb-2">应用发生错误</h2>
            <p className="text-xs text-text-dim mb-4">
              {this.state.error?.message || '未知错误'}
            </p>
            <pre className="text-2xs text-text-dim bg-ide-panel border border-ide-border rounded p-3 mb-4 text-left overflow-auto max-h-32">
              {this.state.error?.stack?.split('\n').slice(0, 5).join('\n')}
            </pre>
            <button
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-white rounded text-xs font-medium hover:bg-accent-hover transition-colors"
            >
              <RotateCcw size={14} />
              重试
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
