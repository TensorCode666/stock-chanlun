import { describe, it, expect } from 'vitest'
import { parsePcScreenFiltersJson, parseMobileScreenFiltersJson } from './exportScreenFiltersJson'

describe('exportScreenFiltersJson parse', () => {
  it('parses valid PC payload', () => {
    const raw = JSON.stringify({
      version: 1,
      platform: 'pc',
      filters: { industry: '银行', pool_size: 200, selectedSignals: ['一买'] },
    })
    const parsed = parsePcScreenFiltersJson(raw)
    expect(parsed?.industry).toBe('银行')
    expect(parsed?.pool_size).toBe(200)
    expect(parsed?.selectedSignals).toEqual(['一买'])
  })

  it('rejects wrong platform or version', () => {
    expect(parsePcScreenFiltersJson('{}')).toBeNull()
    expect(parsePcScreenFiltersJson(JSON.stringify({ version: 2, platform: 'pc', filters: {} }))).toBeNull()
    expect(parsePcScreenFiltersJson(JSON.stringify({ version: 1, platform: 'mobile', filters: {} }))).toBeNull()
  })

  it('parses valid mobile payload', () => {
    const raw = JSON.stringify({
      version: 1,
      platform: 'mobile',
      filters: { signals: '一买', pe_max: 30 },
    })
    const parsed = parseMobileScreenFiltersJson(raw)
    expect(parsed?.signals).toBe('一买')
    expect(parsed?.pe_max).toBe(30)
  })
})
