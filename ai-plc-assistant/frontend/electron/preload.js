const { contextBridge } = require('electron')

// V0.1 骨架阶段 — 仅暴露最小接口
contextBridge.exposeInMainWorld('electronAPI', {
  getAppVersion: () => '0.1.0',
})
