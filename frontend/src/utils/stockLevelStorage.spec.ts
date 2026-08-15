import { describe, it, expect, beforeEach } from 'vitest'
import { getStockLevel, setStockLevel, resolveStockLevel } from './stockLevelStorage'

function mockLocalStorage() {
  const store = new Map<string, string>()
  const ls = {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => { store.set(k, v) },
    removeItem: (k: string) => { store.delete(k) },
    clear: () => { store.clear() },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: ls, configurable: true })
}

describe('stockLevelStorage', () => {
  beforeEach(() => {
    mockLocalStorage()
    localStorage.clear()
  })

  it('returns null for unknown code', () => {
    expect(getStockLevel('600519')).toBeNull()
  })

  it('persists and reads level per code', () => {
    setStockLevel('600519', 'weekly')
    expect(getStockLevel('600519')).toBe('weekly')
    expect(getStockLevel('000001')).toBeNull()
  })

  it('resolveStockLevel validates code format', () => {
    setStockLevel('600519', '30min')
    expect(resolveStockLevel('600519')).toBe('30min')
    expect(resolveStockLevel('abc')).toBeNull()
    // 实现会对 code 先 trim，因此带空白的合法代码也能解析到已记忆级别
    expect(resolveStockLevel(' 600519 ')).toBe('30min')
  })
})
