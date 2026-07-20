/**
 * 运行环境识别模块
 *
 * 提供统一的运行环境判断，避免业务代码散落 Electron/Web 判断。
 *
 * 使用：
 *   import { isElectron, isWeb, getRuntimeMode } from '../platform/runtime'
 *   if (isElectron()) { ... }
 */

/**
 * 是否在 Electron 桌面环境
 *
 * Electron preload 通过 contextBridge 暴露 electronAPI 对象，
 * 业务代码可通过 window.electronAPI 判断运行环境。
 *
 * 见 electron/preload.js：
 *   contextBridge.exposeInMainWorld('electronAPI', { getAppVersion: () => '0.1.0' })
 */
export function isElectron() {
  return typeof window !== 'undefined' && !!window.electronAPI
}

/**
 * 是否在 Web 浏览器环境
 */
export function isWeb() {
  return !isElectron()
}

/**
 * 获取运行模式
 * @returns {'electron' | 'web'}
 */
export function getRuntimeMode() {
  return isElectron() ? 'electron' : 'web'
}

/**
 * Electron API 安全访问器
 *
 * 在 Web 模式下返回 undefined，业务代码可直接 optional chaining：
 *   const ver = getElectronAPI()?.getAppVersion?.()
 *
 * @returns {object | undefined}
 */
export function getElectronAPI() {
  return typeof window !== 'undefined' ? window.electronAPI : undefined
}
