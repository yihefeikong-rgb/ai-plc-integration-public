import { useState, useEffect } from 'react'
import { getModels } from '../api'

export default function useModels() {
  const [models, setModels] = useState([{ id: 'deepseek', name: 'DeepSeek', enabled: true }])
  const [selectedModel, setSelectedModel] = useState('deepseek')
  // 修复：模型列表加载失败不再静默吞掉；通过 error 状态暴露给调用方，
  // 使其能区分真实模型列表与硬编码兜底（fail-closed：失败可见而非假装成功）
  const [error, setError] = useState(null)

  useEffect(() => {
    getModels().then(d => {
      if (d.models) {
        setModels(d.models)
        const enabled = d.models.find(m => m.enabled)
        if (enabled) setSelectedModel(enabled.id)
      }
    }).catch(err => {
      setError(err)
    })
  }, [])

  return { models, selectedModel, setSelectedModel, error }
}
