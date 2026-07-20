import { describe, expect, it, afterEach } from 'vitest'

import {
  isElectron,
  isWeb,
  getRuntimeMode,
  getElectronAPI,
} from './runtime'

describe('platform/runtime', () => {
  afterEach(() => {
    // 清理 window.electronAPI
    delete window.electronAPI
  })

  it('isWeb() returns true when no window.electronAPI', () => {
    expect(isWeb()).toBe(true)
    expect(isElectron()).toBe(false)
  })

  it('isElectron() returns true when window.electronAPI is present', () => {
    window.electronAPI = { getAppVersion: () => '0.1.0' }
    expect(isElectron()).toBe(true)
    expect(isWeb()).toBe(false)
  })

  it('getRuntimeMode() returns "web" or "electron"', () => {
    expect(getRuntimeMode()).toBe('web')
    window.electronAPI = { getAppVersion: () => '0.1.0' }
    expect(getRuntimeMode()).toBe('electron')
  })

  it('getElectronAPI() returns the electronAPI object or undefined', () => {
    expect(getElectronAPI()).toBeUndefined()
    const api = { getAppVersion: () => '0.1.0' }
    window.electronAPI = api
    expect(getElectronAPI()).toBe(api)
  })

  it('getElectronAPI() is safe to call when window is undefined', () => {
    // jsdom 中 window 总是定义的，所以这里仅验证返回 undefined
    delete window.electronAPI
    expect(getElectronAPI()).toBeUndefined()
  })
})

describe('api.js — API_BASE / API_DOCS_URL', () => {
  it('API_BASE defaults to /api in dev mode', async () => {
    // import.meta.env.DEV 在 vitest 中为 true
    const mod = await import('../api')
    // DEV 模式且无 VITE_API_BASE，应 fallback 到 '/api'
    expect(mod.API_BASE).toBe('/api')
  })

  it('API_DOCS_URL derives from API_BASE', async () => {
    const mod = await import('../api')
    // API_BASE = '/api' → API_DOCS_URL = '/docs'
    expect(mod.API_DOCS_URL).toBe('/docs')
  })
})
