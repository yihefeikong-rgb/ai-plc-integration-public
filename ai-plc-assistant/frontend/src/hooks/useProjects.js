import { useState, useRef } from 'react'
import { createProject, importProject } from '../api'

export default function useProjects({ addLog }) {
  const [currentProject, setCurrentProject] = useState(null)
  const importRef = useRef(null)

  const handleCreateProject = async (data) => {
    const name = typeof data === 'string' ? data : data?.name
    if (!name?.trim()) return
    try {
      const d = await createProject({
        name: name.trim(),
        plc_type: data?.plcType || 'S7-1200',
        tia_version: data?.tiaVersion || 'V18',
        language: data?.language || 'SCL',
      })
      setCurrentProject(d.project)
      addLog('info', `[项目] 创建: ${name.trim()}`)
    } catch (err) { addLog('error', `[项目] ${err.message}`) }
  }

  const handleImportProject = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    addLog('info', `[导入] ${file.name} (${(file.size / 1024 / 1024).toFixed(1)}MB)`)
    try {
      const d = await importProject(file)
      setCurrentProject(d.project)
      addLog('info', `[导入] 完成: ${d.project.name} — ${d.index.files_scanned}文件, ${d.index.entries_indexed}条目`)
    } catch (err) {
      addLog('error', `[导入] 失败: ${err.message}`)
    }
    e.target.value = ''
  }

  return { currentProject, setCurrentProject, handleCreateProject, handleImportProject, importRef }
}
