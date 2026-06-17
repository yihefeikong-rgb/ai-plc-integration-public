import { useState, useEffect } from 'react'
import { getModels } from '../api'

export default function useModels() {
  const [models, setModels] = useState([{ id: 'deepseek', name: 'DeepSeek', enabled: true }])
  const [selectedModel, setSelectedModel] = useState('deepseek')

  useEffect(() => {
    getModels().then(d => {
      if (d.models) {
        setModels(d.models)
        const enabled = d.models.find(m => m.enabled)
        if (enabled) setSelectedModel(enabled.id)
      }
    }).catch(() => {})
  }, [])

  return { models, selectedModel, setSelectedModel }
}
