/** 每只股票记住上次查看的 K 线级别 */
import type { LevelOption } from '@/stores/chanlun'

const KEY = 'chanstock_stock_levels_v1'

export function getStockLevel(code: string): LevelOption | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const map = JSON.parse(raw) as Record<string, LevelOption>
    return map[code] ?? null
  } catch {
    return null
  }
}

export function setStockLevel(code: string, level: LevelOption) {
  try {
    const raw = localStorage.getItem(KEY)
    const map = raw ? (JSON.parse(raw) as Record<string, LevelOption>) : {}
    map[code] = level
    localStorage.setItem(KEY, JSON.stringify(map))
  } catch {
    /* quota */
  }
}
